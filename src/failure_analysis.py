"""CP4: visualize a fixed pedestrian point cohort losing its 2D association.

Run from repo root: python -m src.failure_analysis
Source image and labels: KITTI Vision Benchmark Suite, provided course subset.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from starter.datasets import load_frame
from starter.projection import perturb_extrinsic, project_velo_to_image, velo_to_cam
from src.yaw_benchmark import matched_points, points_in_box, write_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    figures = args.out_dir / "figures"
    figures.mkdir(exist_ok=True)
    frame_id, object_id = "000011", 5
    frame = load_frame("data/kitti_mini", frame_id)
    obj = frame["labels"][object_id]
    _, _, baseline_fov = project_velo_to_image(frame["points"], frame["calib"], frame["image"].shape)
    fixed = points_in_box(velo_to_cam(frame["points"][:, :3], frame["calib"]), obj) & baseline_fov
    count = int(fixed.sum())
    if not count:
        raise ValueError("Selected failure object has no baseline points")
    finite_count = int(np.isfinite(frame["points"][:, :3]).all(axis=1).sum())
    rows, projections = [], {}
    baseline_uv = None
    width = float(obj.bbox[2] - obj.bbox[0])
    for yaw in (0., 0.5, 1., 2., 3.):
        uv, _, fov = project_velo_to_image(
            frame["points"], perturb_extrinsic(frame["calib"], yaw_deg=yaw), frame["image"].shape)
        full = np.full((len(fov), 2), np.nan)
        full[fov] = uv
        selected_uv = full[fixed]
        if baseline_uv is None:
            baseline_uv = selected_uv.copy()
        visible = np.isfinite(selected_uv).all(axis=1)
        matched = matched_points(selected_uv, obj.bbox)
        displacement = selected_uv[visible] - baseline_uv[visible]
        rows.append(dict(dataset="kitti_mini", frame_id=frame_id, object_id=object_id,
                         class_name=obj.type, depth_m=float(obj.location[2]), yaw_deg=yaw,
                         baseline_pairs=count, matched_pairs=int(matched.sum()),
                         object_points_in_fov=int(visible.sum()), object_match_pct=100 * matched.sum() / count,
                         median_horizontal_shift_px=float(np.median(displacement[:, 0])) if len(displacement) else "",
                         median_pixel_displacement=float(np.median(np.linalg.norm(displacement, axis=1))) if len(displacement) else "",
                         bbox_width_px=width, frame_inside_fov_pct=100 * fov.sum() / finite_count))
        projections[yaw] = (selected_uv, matched)
    write_csv(args.out_dir / "failure_case_metrics.csv", rows)
    fig, axes = plt.subplots(2, 2, figsize=(13, 7), constrained_layout=True)
    image = cv2.cvtColor(frame["image"], cv2.COLOR_BGR2RGB)
    x1, y1, x2, y2 = obj.bbox
    # The same crop in both panels includes the box and the displaced point cloud.
    pixels = np.vstack([projections[y][0] for y in (0., 3.)])
    valid_pixels = pixels[np.isfinite(pixels).all(axis=1)]
    left = max(0, min(x1, valid_pixels[:, 0].min()) - 30)
    right = min(image.shape[1], max(x2, valid_pixels[:, 0].max()) + 30)
    top, bottom = max(0, y1 - 25), min(image.shape[0], y2 + 25)
    for col, yaw in enumerate((0., 3.)):
        pixels, matched = projections[yaw]
        row = rows[0 if yaw == 0 else -1]
        for level in (0, 1):
            ax = axes[level, col]
            ax.imshow(image)
            ax.add_patch(plt.Rectangle((x1, y1), x2 - x1, y2 - y1,
                                      fill=False, edgecolor="#00dfdd", linewidth=2))
            for hit, color in [(True, "#32d74b"), (False, "#ff3030")]:
                pts = pixels[(matched == hit) & np.isfinite(pixels).all(axis=1)]
                ax.scatter(pts[:, 0], pts[:, 1], s=9 if level == 0 else 20,
                           c=color, edgecolors="black", linewidths=0.2)
            if level == 0:
                ax.set_title(f"yaw {yaw:g} deg | match {row['matched_pairs']}/{count} | "
                             f"object FOV {row['object_points_in_fov']}/{count}")
                ax.set_xlim(0, image.shape[1])
                ax.set_ylim(image.shape[0], 0)
                ax.set_axis_off()
            else:
                ax.set_title(f"Same crop | median horizontal shift {row['median_horizontal_shift_px']:.2f} px")
                ax.set_xlim(left, right)
                ax.set_ylim(bottom, top)
                ax.set_xlabel("Original image u (pixels)")
                ax.set_ylabel("Original image v (pixels)")
    fig.suptitle(f"KITTI {frame_id}, object {object_id}: {obj.type}, depth {obj.location[2]:.2f} m, box width {width:.2f} px\n"
                 f"Fixed {count} baseline object points | cyan: label box | green: match | red: mismatch", fontsize=12)
    fig.savefig(figures / "fail_01_yaw_3deg_pedestrian.png", dpi=150)
    plt.close(fig)
    for row in rows:
        print(f"yaw={row['yaw_deg']:g}: match={row['matched_pairs']}/{count}, "
              f"object FOV={row['object_points_in_fov']}/{count}, "
              f"shift={row['median_horizontal_shift_px']:.3f}px, frame FOV={row['frame_inside_fov_pct']:.5f}%")


if __name__ == "__main__":
    main()
