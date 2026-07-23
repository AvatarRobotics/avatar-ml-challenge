Robot URDF — challenge share bundle

Contents
--------
  agibot_g1.urdf   Flat URDF for the dual-arm robot with finger grippers
                   on both wrists. Mesh references are relative paths
                   (meshes/<name>.STL) so the bundle is self-contained for
                   non-ROS consumers (Foxglove, pybullet, IsaacSim, Drake, etc.).
  meshes/          STL mesh files referenced by the URDF.

Notes
-----
  * The robot's "lift" prismatic joint has 0.5 m of travel; the URDF nominal
    pose has it at 0.
  * Each arm has 7 revolute DOFs (joint1..joint7) plus a fixed camera_mount
    frame at the wrist and a fixed gripper_center frame as the IK tip
    (227 mm beyond the gripper base along its local +Z).
  * Finger joints are modeled with mimic joints driven from joint1; the
    underlying mechanism is a 5-bar linkage, so the mimic relationship is
    approximate but adequate for visualization and reach planning.

The URDF filename and robot name attributes are historical; treat this as
"the challenge robot" for the exercise.
