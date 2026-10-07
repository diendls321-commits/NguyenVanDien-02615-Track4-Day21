# Báo cáo Day 6: Độ nhạy của phép chiếu LiDAR-camera với lệch yaw

> Thay **mọi** ô có chữ ĐIỀN nằm trong ngoặc vuông bằng nội dung của bạn, xoá luôn cả dấu ngoặc vuông. Lệnh `python tools/check_submission.py` sẽ báo FAIL nếu còn sót bất kỳ chỗ nào.

- **Họ tên:** Nguyễn Văn Diện
- **MSSV:** 02615 
- **Lớp:** AI20K-T4
- **Link repo:** https://github.com/diendls321-commits/NguyenVanDien-02615-Track4-Day21
- **Topic:** A — LiDAR-camera projection QA; mục tiêu mức Good.
- **Dataset:** `data/kitti_mini` và `data/nuscenes_mini_subset` cho thí nghiệm chính; `data/synthetic` để kiểm tra code.
- **Các frame dự kiến dùng (đã xác nhận bằng `list_frames`):** KITTI: `000001, 000004, 000007, 000008, 000009, 000010, 000011, 000012, 000015, 000016, 000019, 000021, 000023, 000025, 000031, 000032, 000043, 000048, 000049, 000061` (20 frame). nuScenes: mọi frame từ `scene-0103_000` đến `scene-0103_039` và từ `scene-1094_000` đến `scene-1094_039`, bao gồm hai đầu (80 frame). Synthetic: `000000–000004` (5 frame).

> Hãy viết ngắn: mỗi mục từ 3 đến 8 dòng, ưu tiên số liệu và hình ảnh.

## 1. Claim

**Giả thuyết CP1:** Trên từng dataset KITTI mini và nuScenes mini subset, lệch yaw +3° quanh trục z của LiDAR làm tỷ lệ điểm thuộc vật thể chiếu đúng vào box 2D tương ứng giảm ít nhất **5 điểm phần trăm** so với calibration gốc (0°).

**Kết luận CP3:** Giả thuyết được ủng hộ trên tập frame đã chọn: KITTI giảm **26,34 điểm phần trăm** (99,41% → 73,06%); nuScenes giảm **29,99 điểm phần trăm** (99,93% → 69,94%). Đây là kết quả trên subset và cách đo dưới đây, chưa suy rộng thành ngưỡng cảnh báo cho mọi sensor hay scene.

- Sweep dự kiến: yaw `0°, +0.5°, +1°, +2°, +3°`; chỉ thay đổi yaw, giữ nguyên frame, point cloud, label, calibration gốc và bộ lọc. Seed cấu hình: `42`; phép chiếu không dùng ngẫu nhiên. nuScenes giữ `use_ego_motion=True` ở mọi mức.
- Chọn class `Car, Pedestrian, Cyclist, Bicycle` nếu có trong dataset; bỏ `DontCare` và box không hợp lệ. Xác định điểm thuộc từng box 3D bằng calibration **gốc**, rồi giữ cố định tập điểm đó khi perturb; không chọn lại điểm theo calibration đã lệch.
- Metric chính: số cặp điểm–vật thể baseline chiếu vào đúng box 2D tương ứng sau perturb / số cặp điểm–vật thể thuộc box 3D và có phép chiếu hợp lệ ở baseline. Tập cặp này cố định ở cả 5 mức; điểm ra ngoài ảnh sau perturb tính là không khớp. Tổng hợp bằng tổng tử số / tổng mẫu số riêng từng dataset, ưu tiên vật thể có nhiều điểm; một điểm thuộc hai box được tính thành hai cặp. Box không có điểm baseline được ghi nhận nhưng không đưa vào tỷ lệ.
- Metric bổ sung: tỷ lệ điểm trong FOV trên tổng số điểm XYZ hữu hạn; phân tích theo độ sâu camera baseline `<15 m`, `15–30 m`, `≥30 m`. Box 2D chỉ là chỉ số thay thế cho alignment, không chứng minh độ chính xác calibration tuyệt đối; KITTI và nuScenes có cách tạo label khác nhau.
- Kiểm tra dữ liệu ban đầu: `results/data_health.csv` được tạo bằng starter trên 5 frame synthetic; mỗi frame có khoảng `0,10%` điểm không hợp lệ, frame `000003` có 22.063 điểm so với khoảng 23.760–23.953 ở các frame còn lại. NaN/Inf được lọc trước phép chiếu.

## 2. Evidence

**Benchmark CP3:** toàn bộ 20 frame KITTI và 80 frame nuScenes × 5 mức yaw = 500 cấu hình frame. Chỉ xoay quanh trục z-up của LiDAR, ghép bên phải vào extrinsic; không dịch chuyển, không đổi pitch/roll, không thay dữ liệu hoặc label. Bật bù ego motion của starter cho nuScenes ở mọi mức; chưa bù chuyển động riêng của vật thể.

| Yaw (°) | Khớp box KITTI (%) | Khớp box nuScenes (%) | FOV KITTI (%) | FOV nuScenes (%) |
|---|---|---|---|---|
| 0 | 99,41 | 99,93 | 15,7396 | 8,7266 |
| 0,5 | 96,76 | 97,61 | 15,7466 | 8,7233 |
| 1 | 91,84 | 92,16 | 15,7498 | 8,7234 |
| 2 | 81,78 | 80,53 | 15,7514 | 8,7176 |
| 3 | 73,06 | 69,94 | 15,7597 | 8,7117 |

![Sweep yaw và phân nhóm độ sâu](../results/figures/yaw_perturb_sweep.png)

- Mẫu số khớp box cố định: KITTI **28.704 cặp**, nuScenes **17.337 cặp**; 259 box nuScenes không có điểm baseline hợp lệ, được ghi nhận riêng và không đóng góp vào tỷ lệ. Vì vậy score không đánh giá khả năng phát hiện vật thể không có điểm LiDAR.
- Nhóm xa ≥30 m giảm từ **99,35% → 15,78%** trên KITTI (773 cặp), **100% → 12,96%** trên nuScenes (818 cặp); nhóm gần <15 m còn **81,50%** và **80,05%** ở 3°. Trong tập này vật xa nhạy hơn, nhưng ít điểm nên cần xem từng vật thể; không coi là quy luật đã xác nhận cho mọi scene.
- FOV gần như không đổi (0° → 3°: KITTI **+0,0201**, nuScenes **−0,0149 điểm phần trăm**), dù độ khớp box giảm mạnh. Chỉ số FOV một mình không đủ đánh giá lệch calibration. nuScenes có FOV thấp hơn ở subset này; sensor, cảnh và nội suy label khác nhau, nên không kết luận số beam là nguyên nhân duy nhất. Box 2D nuScenes được starter tạo từ box 3D, không phải label ảnh độc lập; baseline gần 100% có tính phụ thuộc vào hình học đó.
- Số liệu: `results/yaw_perturb_sweep.csv` (40 dòng tổng hợp), `results/yaw_perturb_frames.csv` (500 dòng), `results/yaw_perturb_objects.csv` (23.460 dòng theo vật thể, yaw và nhóm độ sâu). Frame, class, seed 42 và cách đo lưu trong `results/yaw_benchmark_config.json`; seed chỉ được ghi cấu hình vì thí nghiệm không dùng ngẫu nhiên.
- Tái lập: chạy độc lập hai lần, cả **3 CSV và JSON cấu hình có SHA256 giống hệt**; kiểm tra đủ 100 frame, mẫu số cố định, số khớp không vượt mẫu số đều PASS. Sáu test phép chiếu/box/metric đều PASS. Ảnh so sánh [KITTI 0°–3°](../results/figures/yaw_comparison_kitti_mini_000011.png) và [nuScenes 0°–3°](../results/figures/yaw_comparison_nuscenes_mini_subset_scene-0103_010.png) được tạo bằng cùng input và cùng thang màu.

**Baseline CP2, yaw 0°:** đã hoàn thiện phép biến đổi `R0_rect · Tr_velo_to_cam` và phép chiếu bằng `P2`; lọc XYZ NaN/Inf, độ sâu camera ≤0,1 m và pixel ngoài ảnh. Tỷ lệ FOV dưới đây có mẫu số là số điểm XYZ hữu hạn, không phải số điểm trên vật thể.

| Dataset / frame demo | Điểm trong FOV | FOV (%) | Ghi chú |
|---|---|---|---|
| Synthetic / 000000 | 3.910 / 23.930 | 16,34 | Lọc 23 điểm XYZ không hợp lệ |
| KITTI / 000011 | 19.946 / 108.004 | 18,47 | Gần: 11.374; trung bình: 6.578; xa: 1.994 điểm |
| nuScenes / scene-0103_010 | 3.120 / 34.720 | 8,99 | Ban ngày, bật bù ego motion |
| nuScenes / scene-1094_010 | 3.592 / 34.688 | 10,36 | Ban đêm, bật bù ego motion |

![Demo KITTI, màu theo độ sâu](../results/figures/demo_kitti_000011_all.png)

Ba ảnh khoảng cách: [gần <15 m](../results/figures/demo_kitti_000011_near.png), [trung bình 15–30 m](../results/figures/demo_kitti_000011_mid.png), [xa ≥30 m](../results/figures/demo_kitti_000011_far.png), theo độ sâu camera, cùng frame và calibration.
Demo [synthetic](../results/figures/demo_synthetic_000000_all.png), [nuScenes ban ngày](../results/figures/demo_nuscenes_day_scene-0103_010_all.png), [nuScenes ban đêm](../results/figures/demo_nuscenes_night_scene-1094_010_all.png); dữ liệu ảnh: KITTI Vision Benchmark Suite và nuScenes (Motional).
Số đếm lưu tại `results/projection_demo.csv`; các ảnh có box 2D màu xanh lá và điểm màu đỏ gần → xanh dương xa (thang màu bão hòa ở 50 m). Đây là các frame demo, khác với số liệu tổng hợp toàn bộ 100 frame ở bảng CP3 phía trên.

## 3. Failure case

**Case CP4:** KITTI `000011`, object index `5` trong danh sách label của starter, class `Pedestrian`, độ sâu camera đáy box **15,95 m**, label không che khuất (`occluded=0`). Box ảnh `[240,35; 190,31; 268,02; 261,61]` rộng **27,67 pixel**. Giữ cố định 81 điểm thuộc box 3D và nằm trong FOV ở calibration gốc; chỉ thay đổi yaw.

![Failure: điểm người đi bộ lệch khỏi box dù vẫn nằm trong ảnh](../results/figures/fail_01_yaw_3deg_pedestrian.png)

| Yaw (°) | Điểm khớp box / 81 | Điểm vẫn trong ảnh / 81 | Trung vị dịch ngang (pixel) |
|---|---|---|---|
| 0 | 81 | 81 | 0,00 |
| 0,5 | 66 | 81 | −7,99 |
| 1 | 28 | 81 | −16,06 |
| 2 | 0 | 81 | −32,41 |
| 3 | 0 | 81 | −49,08 |

- **Sai ở đâu:** ở yaw 3°, cùng các điểm trên người bị chiếu sang trái box khoảng 49,08 pixel theo trung vị, lớn hơn chiều rộng box 27,67 pixel. Ảnh giữ nguyên box màu cyan; điểm xanh là khớp, đỏ là không khớp. Cả 81 điểm vẫn xuất hiện trong ảnh; liên kết LiDAR–vật thể bằng box 2D mất hoàn toàn từ mức 2° đã thử. Đây là lỗi liên kết hình học, chưa phải bằng chứng detector bỏ sót người.
- **Nguyên nhân gốc — Geometry:** extrinsic dùng khi chiếu bị ghép thêm rotation yaw, nên hướng tia LiDAR trong hệ camera thay đổi. Point cloud, ảnh và label đều giữ nguyên, tập điểm chọn bằng box 3D baseline cũng giữ nguyên. Khi dùng lại calibration gốc 0°, phép chiếu khớp 81/81. Thí nghiệm cô lập lỗi Geometry; không dùng model, không thay timestamp hay preprocessing để tạo failure.
- **Giới hạn cách phát hiện — Metric:** FOV toàn frame chỉ đổi **18,46783% → 18,46969%**, tăng 0,00185 điểm phần trăm, trong khi score của người này giảm **100% → 0%**. Một cảnh báo giả định chỉ dựa vào mất điểm khỏi FOV sẽ không phát hiện case này; đề tài chưa xây dựng hoặc đánh giá bộ cảnh báo tự động.
- **Phát hiện/khắc phục khi triển khai:** theo dõi độ khớp LiDAR–ảnh theo từng vật thể và nhóm độ sâu, kèm số điểm hỗ trợ; FOV chỉ là chỉ số phụ. Trên xe không có GT, cần kiểm chứng thêm score dựa trên biên ảnh/độ sâu hoặc detection độc lập, kiểm tra time sync và giá đỡ sensor trước khi recalibrate. Ngưỡng cảnh báo phải được hiệu chỉnh trên tập riêng; khi nghi ngờ drift, giảm phụ thuộc vào fusion camera–LiDAR và kiểm tra calibration.
- **Tái tạo và đối chiếu:** `python -m src.failure_analysis` tạo ảnh cùng `results/failure_case_metrics.csv`; số cặp baseline và số khớp ở cả 5 mức khớp chính xác các dòng tương ứng của `results/yaw_perturb_objects.csv` từ CP3. Nguồn ảnh: KITTI Vision Benchmark Suite; chỉ vẽ điểm của người được chọn để làm rõ failure.

## 4. Khuyến nghị nếu triển khai thật

Use-case cụ thể (ADAS / robot / drone), trade-off và bước tiếp theo.

[ĐIỀN]

## 5. Cách chạy lại

Chạy từ thư mục gốc repo với Python ≥3.10. Các lệnh hiện tái tạo kết quả CP1–CP4.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m starter.data_health --data-root data/synthetic
python -m unittest src.test_projection src.test_yaw_benchmark -v
python -m src.projection_demo
python -m src.yaw_benchmark
python -m src.failure_analysis
# Optional: independent replay into another output directory
python -m src.yaw_benchmark --out-dir results/replay
```

Kiểm tra độc lập CP2: điểm LiDAR `(10, 0, 0)` của synthetic `000000` cho `z_cam=9,727321 m`, pixel `(613,964149; 175,006537)`, khớp mốc đề bài `(614; 175)`. Bốn test kiểm tra điểm tham chiếu, rectification + translation, NaN/Inf + điểm sau camera + biên ảnh, phép chia tọa độ đồng nhất + đầu vào rỗng đều PASS.

## 6. Khai báo sử dụng AI

Ghi rõ đã dùng công cụ AI nào, dùng vào việc gì, và bạn đã tự kiểm chứng kết quả đó bằng cách nào. Nếu không dùng AI, ghi "Không sử dụng". Xem quy định ở `RULES.md` mục 2.

| Công cụ | Dùng cho việc gì | Bạn đã kiểm chứng thế nào |
|---|---|---|
| Codex (OpenAI) | Thiết kế CP1; viết projection, demo, benchmark yaw, test geometry/metric, script failure, tạo CSV/plot và cập nhật báo cáo CP2–CP4 | Agent đã chạy điểm tham chiếu, 6 test, xem ảnh/plot, chạy benchmark hai lần trên 100 frame; 3 CSV và JSON cấu hình giống SHA256, mẫu số cố định PASS. Số liệu failure CP4 được đối chiếu với CP3 ở cả 5 mức yaw. Học viên cần tự chạy lại và giải thích kết quả; chưa xác nhận việc tự kiểm chứng của học viên |
