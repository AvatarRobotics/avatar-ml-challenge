"""Minimal URDF forward-kinematics helpers for the challenge replay viewer.

Self-contained (no ROS). Parses a flat URDF, computes link poses from joint
positions. Used by replay_dataset.py.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


def _rpy_to_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return np.array(
        [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ]
    )


def _axis_angle_to_matrix(axis: tuple[float, ...], angle: float) -> np.ndarray:
    ax, ay, az = axis
    c, s = math.cos(angle), math.sin(angle)
    t = 1.0 - c
    return np.array(
        [
            [t * ax * ax + c, t * ax * ay - s * az, t * ax * az + s * ay],
            [t * ax * ay + s * az, t * ay * ay + c, t * ay * az - s * ax],
            [t * ax * az - s * ay, t * ay * az + s * ax, t * az * az + c],
        ]
    )


def _origin_to_transform(
    xyz: tuple[float, float, float],
    rpy: tuple[float, float, float],
) -> np.ndarray:
    xform = np.eye(4)
    xform[:3, :3] = _rpy_to_matrix(*rpy)
    xform[:3, 3] = xyz
    return xform


@dataclass
class JointInfo:
    name: str
    joint_type: str
    parent_link: str
    child_link: str
    origin_xyz: tuple[float, float, float] = (0.0, 0.0, 0.0)
    origin_rpy: tuple[float, float, float] = (0.0, 0.0, 0.0)
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0)
    mimic_joint: str | None = None
    mimic_multiplier: float = 1.0
    mimic_offset: float = 0.0


@dataclass
class KinematicModel:
    joints: dict[str, JointInfo] = field(default_factory=dict)
    root_link: str = ""

    @classmethod
    def from_urdf(cls, urdf_path: Path) -> KinematicModel:
        tree = ET.parse(urdf_path)
        root = tree.getroot()
        joints: dict[str, JointInfo] = {}
        parent_links: set[str] = set()
        child_links: set[str] = set()

        for joint_elem in root.iter("joint"):
            name = joint_elem.get("name", "")
            joint_type = joint_elem.get("type", "fixed")
            parent_elem = joint_elem.find("parent")
            child_elem = joint_elem.find("child")
            if parent_elem is None or child_elem is None:
                continue
            parent_link = parent_elem.get("link", "")
            child_link = child_elem.get("link", "")
            parent_links.add(parent_link)
            child_links.add(child_link)

            origin_xyz = (0.0, 0.0, 0.0)
            origin_rpy = (0.0, 0.0, 0.0)
            origin_elem = joint_elem.find("origin")
            if origin_elem is not None:
                xyz_str = origin_elem.get("xyz", "0 0 0")
                rpy_str = origin_elem.get("rpy", "0 0 0")
                origin_xyz = tuple(float(v) for v in xyz_str.split())  # type: ignore[assignment]
                origin_rpy = tuple(float(v) for v in rpy_str.split())  # type: ignore[assignment]

            axis = (0.0, 0.0, 1.0)
            axis_elem = joint_elem.find("axis")
            if axis_elem is not None:
                axis = tuple(float(v) for v in axis_elem.get("xyz", "0 0 1").split())  # type: ignore[assignment]

            mimic_joint = None
            mimic_multiplier = 1.0
            mimic_offset = 0.0
            mimic_elem = joint_elem.find("mimic")
            if mimic_elem is not None:
                mimic_joint = mimic_elem.get("joint")
                mimic_multiplier = float(mimic_elem.get("multiplier", "1.0"))
                mimic_offset = float(mimic_elem.get("offset", "0.0"))

            joints[name] = JointInfo(
                name=name,
                joint_type=joint_type,
                parent_link=parent_link,
                child_link=child_link,
                origin_xyz=origin_xyz,
                origin_rpy=origin_rpy,
                axis=axis,
                mimic_joint=mimic_joint,
                mimic_multiplier=mimic_multiplier,
                mimic_offset=mimic_offset,
            )

        root_links = parent_links - child_links
        root_link = sorted(root_links)[0] if root_links else ""
        return cls(joints=joints, root_link=root_link)

    def _resolve_position(self, joint: JointInfo, joint_positions: dict[str, float]) -> float:
        if joint.mimic_joint is not None:
            master = joint_positions.get(joint.mimic_joint, 0.0)
            return master * joint.mimic_multiplier + joint.mimic_offset
        return joint_positions.get(joint.name, 0.0)

    def compute_joint_transform(self, joint: JointInfo, position: float = 0.0) -> np.ndarray:
        origin = _origin_to_transform(joint.origin_xyz, joint.origin_rpy)
        if joint.joint_type == "fixed":
            return origin
        if joint.joint_type in ("revolute", "continuous"):
            motion = np.eye(4)
            motion[:3, :3] = _axis_angle_to_matrix(joint.axis, position)
            return origin @ motion
        if joint.joint_type == "prismatic":
            motion = np.eye(4)
            motion[:3, 3] = np.array(joint.axis) * position
            return origin @ motion
        return origin

    def link_poses(self, joint_positions: dict[str, float]) -> dict[str, np.ndarray]:
        """Return world pose (4x4) for every link."""
        children: dict[str, list[JointInfo]] = {}
        for j in self.joints.values():
            children.setdefault(j.parent_link, []).append(j)

        poses: dict[str, np.ndarray] = {self.root_link: np.eye(4)}
        stack = [self.root_link]
        while stack:
            parent = stack.pop()
            parent_pose = poses[parent]
            for joint in children.get(parent, []):
                pos = self._resolve_position(joint, joint_positions)
                child_pose = parent_pose @ self.compute_joint_transform(joint, pos)
                poses[joint.child_link] = child_pose
                stack.append(joint.child_link)
        return poses

    def skeleton_segments(
        self, joint_positions: dict[str, float]
    ) -> list[tuple[np.ndarray, np.ndarray]]:
        """Return list of (parent_xyz, child_xyz) segments for stick-figure draw."""
        poses = self.link_poses(joint_positions)
        segs: list[tuple[np.ndarray, np.ndarray]] = []
        for joint in self.joints.values():
            if joint.parent_link not in poses or joint.child_link not in poses:
                continue
            p = poses[joint.parent_link][:3, 3]
            c = poses[joint.child_link][:3, 3]
            segs.append((p.copy(), c.copy()))
        return segs


# Common name maps: LeRobot joint_1..7 (one arm) → URDF joint names.
LEFT_ARM_URDF = [f"left_arm_joint{i}" for i in range(1, 8)]
RIGHT_ARM_URDF = [f"right_arm_joint{i}" for i in range(1, 8)]


def state_to_joint_dict(
    state: np.ndarray,
    arm: str = "right",
    include_other_arm_zero: bool = True,
) -> dict[str, float]:
    """Map observation.state[0:7] to URDF joint names for one arm."""
    names = LEFT_ARM_URDF if arm == "left" else RIGHT_ARM_URDF
    other = RIGHT_ARM_URDF if arm == "left" else LEFT_ARM_URDF
    d = {n: float(state[i]) for i, n in enumerate(names[: min(7, len(state))])}
    if include_other_arm_zero:
        for n in other:
            d.setdefault(n, 0.0)
    return d
