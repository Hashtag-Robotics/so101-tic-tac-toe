# Bench assembly and camera contract

1. Clamp or bolt both SO-101 bases to a rigid work surface.
2. Place the hashtag board flat and prevent it from sliding.
3. Place one pickup-zone frame on each side used during data collection, keeping
   both completely inside the corresponding arm's safe reach.
4. Put six red X tokens in the X zone and six light-grey O tokens in the O zone.
5. Fasten the camera tower to the table, route USB cables down its rear channel
   and keep them outside both arm sweeps.
6. Mount the top camera as `observation.images.top`; mount the wrist camera on
   the arm used by the recorded follower as `observation.images.wrist`.
7. With torque disabled, compare both views to several episodes in the public
   [LeRobot dataset viewer](https://huggingface.co/spaces/lerobot/visualize_dataset?path=HashtagRobotics/tic-tac-toe-so101-block-a-clean-v1).

## Important geometry limitation

The dataset records the actual trained bench but this release does not yet
include a dimensioned base-to-board fixture drawing. Do not infer millimetre
coordinates from this document. The pretrained behavior is sensitive to arm
base position, board/pickup-zone position, top-camera pose, wrist-camera pose,
lighting, token colour and follower calibration.

Until a dimensioned fixture is released, treat visual matching as a diagnostic,
not a calibration method. Perform a torque-off reach check, then a bounded
single-move rollout with the physical E-STOP in hand. If geometry differs,
record/fine-tune for that bench rather than increasing controller limits.

## Coordinate convention

The top camera is rotated 180 degrees relative to the model's task coordinates:

| Top-camera cell | Model/task cell |
| ---: | ---: |
| 1 | 9 |
| 2 | 8 |
| 3 | 7 |
| 4 | 6 |
| 5 | 5 |
| 6 | 4 |
| 7 | 3 |
| 8 | 2 |
| 9 | 1 |

This mapping is enforced by the deterministic controller and must not be
compensated by swapping camera names or mirroring images.
