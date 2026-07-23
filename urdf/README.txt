Agibot G1 URDF — partner share bundle

Contents
--------
  agibot_g1.urdf   Flat URDF for the dual-arm Agibot G1 with the OmniPicker
                   finger gripper on both wrists. Mesh references are
                   relative paths (meshes/<name>.STL) so the bundle is
                   self-contained for non-ROS consumers (Foxglove, pybullet,
                   IsaacSim, Drake, etc.).
  meshes/          32 STL mesh files referenced by the URDF.

Notes
-----
  * The robot's "lift" prismatic joint has 0.5 m of travel; the URDF nominal
    pose has it at 0.
  * Joint naming follows the upstream Agibot convention; each arm has
    7 revolute DOFs (joint1..joint7) plus a fixed camera_mount frame at the
    wrist and a fixed gripper_center frame as the IK tip (227 mm beyond the
    gripper base along its local +Z).
  * OmniPicker fingers are modeled with mimic joints driven from joint1;
    the underlying mechanism is a 5-bar linkage, so the mimic relationship
    is approximate but adequate for visualization and reach planning.

License
-------
  STL meshes and base kinematic data originate from Agibot's published G1
  robot description; redistribution follows Agibot's URDF license terms.
