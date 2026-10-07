"""Reproduce CP2 overlays, including three distinct camera-depth bands.

Uses the course-provided starter loaders and drawing functions.
Run from the repository root: python -m src.projection_demo
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np

from starter.datasets import load_frame
from starter.projection import draw_box2d, overlay_points, project_velo_to_image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("results/figures"))
    parser.add_argument("--summary", type=Path, default=Path("results/projection_demo.csv"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    cases = [
        ("data/synthetic", "000000", "synthetic"),
        ("data/kitti_mini", "000011", "kitti"),
        ("data/nuscenes_mini_subset", "scene-0103_010", "nuscenes_day"),
        ("data/nuscenes_mini_subset", "scene-1094_010", "nuscenes_night"),
    ]
    for root, frame_id, tag in cases:
        frame = load_frame(root, frame_id)
        uv, depth, mask = project_velo_to_image(
            frame["points"], frame["calib"], frame["image"].shape)
        finite = int(np.isfinite(frame["points"][:, :3]).all(axis=1).sum())
        bands = [("all", 0.1, np.inf)]
        if tag == "kitti":
            bands += [("near", 0.1, 15.0), ("mid", 15.0, 30.0), ("far", 30.0, np.inf)]
        for band, lower, upper in bands:
            keep = (depth >= lower) & (depth < upper)
            image = overlay_points(frame["image"], uv[keep], depth[keep], radius=1)
            for obj in frame["labels"]:
                image = draw_box2d(image, obj.bbox, label=obj.type)
            title = f"{tag} {frame_id} | {band} | {int(keep.sum())} points | depth colors: red near, blue far"
            cv2.rectangle(image, (0, 0), (image.shape[1], 27), (0, 0, 0), -1)
            cv2.putText(image, title, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            path = args.out_dir / f"demo_{tag}_{frame_id}_{band}.png"
            if not cv2.imwrite(str(path), image):
                raise OSError(f"Unable to write {path}")
            rows.append(dict(dataset=root, frame_id=frame_id, band=band,
                             n_points=len(mask), n_finite_xyz=finite,
                             n_inside_fov=int(mask.sum()), n_displayed=int(keep.sum()),
                             inside_fov_pct=100 * int(mask.sum()) / finite if finite else 0,
                             output=str(path.as_posix())))
            print(f"{path}: {int(keep.sum())} displayed, {int(mask.sum())}/{finite} finite points in FOV")
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    with args.summary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
