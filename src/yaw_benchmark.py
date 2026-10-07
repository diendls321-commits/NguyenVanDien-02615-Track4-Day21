"""Controlled calibration yaw sweep on every frame of the selected datasets.

The matching score uses fixed point/object pairs selected with baseline 3D
boxes and baseline FOV. It is an offline label-based proxy, not detector recall.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from starter.datasets import list_frames, load_frame
from starter.projection import (draw_box2d, overlay_points, perturb_extrinsic,
                                project_velo_to_image, velo_to_cam)

CLASSES = ("Car", "Pedestrian", "Cyclist", "Bicycle")
BANDS = {"all": (0.1, np.inf), "near": (0.1, 15.),
         "mid": (15., 30.), "far": (30., np.inf)}


def points_in_box(points_cam, obj):
    """Invert KITTI yaw about the bottom center; dimensions are h, w, l."""
    c, s = np.cos(obj.rotation_y), np.sin(obj.rotation_y)
    rotation = np.array([[c, 0., s], [0., 1., 0.], [-s, 0., c]])
    local = (points_cam - obj.location) @ rotation
    h, w, length = obj.dimensions
    return (np.isfinite(local).all(axis=1)
            & (np.abs(local[:, 0]) <= length / 2)
            & (local[:, 1] >= -h) & (local[:, 1] <= 0)
            & (np.abs(local[:, 2]) <= w / 2))


def matched_points(uv_full, bbox):
    """NaN entries represent points outside FOV and must count as misses."""
    x1, y1, x2, y2 = bbox
    return (np.isfinite(uv_full).all(axis=1)
            & (uv_full[:, 0] >= x1) & (uv_full[:, 0] <= x2)
            & (uv_full[:, 1] >= y1) & (uv_full[:, 1] <= y2))


def valid_object(obj):
    return (obj.type in CLASSES and np.isfinite(obj.bbox).all()
            and np.isfinite(obj.dimensions).all() and (obj.dimensions > 0).all()
            and np.isfinite(obj.location).all() and np.isfinite(obj.rotation_y)
            and obj.bbox[2] > obj.bbox[0] and obj.bbox[3] > obj.bbox[1])


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def drift_preview(frame, dataset, frame_id, path):
    panels = []
    for yaw in (0., 3.):
        calib = perturb_extrinsic(frame["calib"], yaw_deg=yaw)
        uv, depth, _ = project_velo_to_image(frame["points"], calib, frame["image"].shape)
        image = overlay_points(frame["image"], uv, depth, radius=1)
        for obj in frame["labels"]:
            if valid_object(obj):
                image = draw_box2d(image, obj.bbox, label=obj.type)
        cv2.rectangle(image, (0, 0), (image.shape[1], 30), (0, 0, 0), -1)
        cv2.putText(image, f"{dataset} {frame_id} | yaw {yaw:g} deg",
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        panels.append(image)
    if not cv2.imwrite(str(path), np.hstack(panels)):
        raise OSError(f"Unable to write {path}")


def plot_summary(summary, out):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for dataset, color in [("kitti_mini", "#1463ad"), ("nuscenes_mini_subset", "#d05b17")]:
        all_rows = [r for r in summary if r["dataset"] == dataset and r["depth_band"] == "all"]
        yaw = [r["yaw_deg"] for r in all_rows]
        axes[0, 0].plot(yaw, [r["object_match_pct"] for r in all_rows], "o-", color=color, label=dataset)
        axes[0, 1].plot(yaw, [r["inside_fov_pct"] for r in all_rows], "o-", color=color, label=dataset)
        ax = axes[1, 0 if dataset == "kitti_mini" else 1]
        for band, label in [("near", "depth <15 m"), ("mid", "depth 15-30 m"), ("far", "depth >=30 m")]:
            rows = [r for r in summary if r["dataset"] == dataset and r["depth_band"] == band]
            ax.plot([r["yaw_deg"] for r in rows], [r["object_match_pct"] for r in rows], "o-", label=label)
        ax.set_title(f"Object matching by baseline depth: {dataset}")
    axes[0, 0].set_title("Points in the corresponding 2D box / fixed baseline pairs")
    axes[0, 1].set_title("Points in FOV / finite XYZ points")
    for ax in axes.flat:
        ax.set_xlabel("LiDAR yaw perturbation (degrees, z-up)")
        ax.set_ylabel("Percent (%)")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
    fig.suptitle("Calibration drift sweep | 20 KITTI + 80 nuScenes frames | fixed baseline cohorts")
    fig.savefig(out, dpi=140)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-roots", nargs="+", default=["data/kitti_mini", "data/nuscenes_mini_subset"])
    parser.add_argument("--yaw-deg", nargs="+", type=float, default=[0., 0.5, 1., 2., 3.])
    parser.add_argument("--out-dir", type=Path, default=Path("results"))
    parser.add_argument("--seed", type=int, default=42, help="Recorded for reproducibility; no random sampling is used")
    args = parser.parse_args()
    if (not args.yaw_deg or not np.isfinite(args.yaw_deg).all()
            or args.yaw_deg[0] != 0 or len(set(args.yaw_deg)) != len(args.yaw_deg)):
        parser.error("Yaw levels must be finite and unique, starting with baseline 0")
    if len({Path(root).name for root in args.data_roots}) != len(args.data_roots):
        parser.error("Dataset folder names must be unique")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    figures = args.out_dir / "figures"
    figures.mkdir(exist_ok=True)
    objects, frames, summary = [], [], []
    config = dict(seed=args.seed, random_sampling=False, yaw_deg=args.yaw_deg,
                  classes=list(CLASSES), min_depth_m=0.1,
                  perturbation="right-compose rotation around native LiDAR z-up; no translation",
                  use_ego_motion=True, depth_bands_m={k: [v[0], None if np.isinf(v[1]) else v[1]] for k, v in BANDS.items()},
                  denominator="fixed point/object pairs: baseline 3D box AND baseline FOV",
                  aggregation="sum matches / sum baseline pairs (point-weighted, not object-weighted)",
                  datasets={})
    for root in args.data_roots:
        dataset = Path(root).name
        ids = list_frames(root)
        if not ids:
            raise ValueError(f"No frames: {root}")
        config["datasets"][dataset] = dict(root=root, frames=ids)
        for index, frame_id in enumerate(ids):
            frame = load_frame(root, frame_id)
            points, calib = frame["points"], frame["calib"]
            camera = velo_to_cam(points[:, :3], calib)
            _, _, baseline_fov = project_velo_to_image(points, calib, frame["image"].shape)
            finite_count = int(np.isfinite(points[:, :3]).all(axis=1).sum())
            cohorts = []
            for object_id, obj in enumerate(frame["labels"]):
                if valid_object(obj):
                    fixed = points_in_box(camera, obj) & baseline_fov
                    cohorts.append((object_id, obj, fixed))
            for yaw in args.yaw_deg:
                uv, _, fov = project_velo_to_image(points, perturb_extrinsic(calib, yaw_deg=yaw), frame["image"].shape)
                uv_full = np.full((len(points), 2), np.nan)
                uv_full[fov] = uv
                for object_id, obj, fixed in cohorts:
                    match = matched_points(uv_full, obj.bbox) & fixed
                    for band, (lower, upper) in BANDS.items():
                        eligible = fixed & (camera[:, 2] >= lower) & (camera[:, 2] < upper)
                        count = int(eligible.sum())
                        hit = int((match & eligible).sum())
                        objects.append(dict(dataset=dataset, frame_id=frame_id, object_id=object_id,
                                            class_name=obj.type, object_depth_m=float(obj.location[2]),
                                            yaw_deg=yaw, depth_band=band, baseline_pairs=count,
                                            matched_pairs=hit, object_match_pct=100 * hit / count if count else "",
                                            seed=args.seed))
                frames.append(dict(dataset=dataset, frame_id=frame_id, yaw_deg=yaw,
                                   n_points=len(points), finite_xyz=finite_count, inside_fov=int(fov.sum()),
                                   inside_fov_pct=100 * int(fov.sum()) / finite_count if finite_count else "",
                                   eligible_objects=len(cohorts), zero_baseline_objects=sum(not c[2].any() for c in cohorts),
                                   camera_lidar_gap_ms=(frame["timestamp_camera_us"] - frame["timestamp_lidar_us"]) / 1000 if "timestamp_camera_us" in frame else "",
                                   seed=args.seed))
            if frame_id in ("000011", "scene-0103_010"):
                drift_preview(frame, dataset, frame_id, figures / f"yaw_comparison_{dataset}_{frame_id}.png")
            if (index + 1) % 10 == 0:
                print(f"{dataset}: {index + 1}/{len(ids)} frames complete", flush=True)
        for band in BANDS:
            baseline_rows = [r for r in objects if r["dataset"] == dataset and r["depth_band"] == band and r["yaw_deg"] == args.yaw_deg[0]]
            for yaw in args.yaw_deg:
                rows = [r for r in objects if r["dataset"] == dataset and r["depth_band"] == band and r["yaw_deg"] == yaw]
                denominator = sum(r["baseline_pairs"] for r in rows)
                numerator = sum(r["matched_pairs"] for r in rows)
                baseline_den = sum(r["baseline_pairs"] for r in baseline_rows)
                baseline_num = sum(r["matched_pairs"] for r in baseline_rows)
                if denominator != baseline_den:
                    raise AssertionError("The point cohort changed across yaw levels")
                frows = [r for r in frames if r["dataset"] == dataset and r["yaw_deg"] == yaw]
                finite = sum(r["finite_xyz"] for r in frows)
                inside = sum(r["inside_fov"] for r in frows)
                score = 100 * numerator / denominator if denominator else np.nan
                baseline_score = 100 * baseline_num / baseline_den if baseline_den else np.nan
                summary.append(dict(dataset=dataset, yaw_deg=yaw, depth_band=band,
                                    n_frames=len(ids), baseline_pairs=denominator, matched_pairs=numerator,
                                    object_match_pct=score, drop_from_first_level_pp=baseline_score - score,
                                    finite_xyz=finite, inside_fov=inside,
                                    inside_fov_pct=100 * inside / finite if finite else np.nan, seed=args.seed))
    if not objects:
        raise ValueError("No eligible objects found")
    write_csv(args.out_dir / "yaw_perturb_objects.csv", objects)
    write_csv(args.out_dir / "yaw_perturb_frames.csv", frames)
    write_csv(args.out_dir / "yaw_perturb_sweep.csv", summary)
    (args.out_dir / "yaw_benchmark_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plot_summary(summary, figures / "yaw_perturb_sweep.png")
    for row in summary:
        if row["depth_band"] == "all":
            print(f"{row['dataset']} yaw={row['yaw_deg']:g}: match={row['object_match_pct']:.4f}% FOV={row['inside_fov_pct']:.4f}% drop={row['drop_from_first_level_pp']:.4f}pp")


if __name__ == "__main__":
    main()
