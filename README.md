# 🗺️ 드론 비행구역 맵 뷰어

카카오맵 위에 브이월드 데이터(행정계 / 비행금지구역 / 비행제한구역 / 관제권)를 겹쳐 보여주는 정적 웹페이지입니다.
지도를 클릭하면 그 지점이 어떤 구역에 겹치는지(중복 포함) 목록으로 보여줍니다.

> ⚠️ 참고용입니다. 군사시설, 고도제한, 임시 비행금지(NOTAM)는 표시되지 않습니다.
> 실제 비행 전에는 반드시 [드론원스톱](https://drone.onestop.go.kr)에서 확인하세요.

## 1. 데이터 준비 (최초 1회)

```bash
pip install requests
export VWORLD_KEY="브이월드_키"        # Windows PowerShell: $env:VWORLD_KEY="브이월드_키"
python scripts/download_data.py
```

- 키를 발급받을 때 등록한 도메인이 `http://localhost:8000`이 아니라면 `--domain`으로 알려주세요.
- 기존에 받아둔 `*.geojson`이 있다면 `data/` 폴더에 넣어도 되지만, 예전 방식은 1,000건에서 잘렸을 수 있어 `--force`로 다시 받는 걸 권장합니다.

## 2. 내 컴퓨터에서 실행

```bash
python -m http.server 8000
```

브라우저에서 http://localhost:8000 을 엽니다. (`index.html`을 더블클릭하면 데이터를 못 읽어요.)

## 3. GitHub Pages로 공개

```bash
git init
git add .
git commit -m "드론 비행구역 맵 뷰어"
git branch -M main
git remote add origin https://github.com/<내아이디>/drone-map.git
git push -u origin main
```

GitHub 저장소 → **Settings → Pages → Branch: `main` / `(root)`** → Save.
잠시 뒤 `https://<내아이디>.github.io/drone-map/` 에서 접속됩니다.

**꼭 해야 하는 것:** [카카오 개발자 콘솔](https://developers.kakao.com) → 내 애플리케이션 → 플랫폼 → Web 사이트 도메인에 아래를 모두 등록하세요.

- `http://localhost:8000`
- `https://<내아이디>.github.io`

## 접속이 안 될 때

| 증상 | 원인 / 해결 |
|---|---|
| 지도가 회색/빈 화면 | 카카오 콘솔에 현재 접속 주소(도메인+포트)가 등록 안 됨 |
| 왼쪽 아래에 "파일 없음" | `python scripts/download_data.py`를 안 했거나 `data/` 를 커밋 안 함 |
| "파일을 불러오지 못했어요" | `file://`로 열었음 → `python -m http.server`로 실행 |
| 다운로드 시 API 오류 | 브이월드 키 만료/도메인 불일치 → `--domain` 확인 또는 키 재발급 |
| `Address already in use` | 포트 사용 중 → `python -m http.server 8080` 후 카카오 콘솔에도 8080 등록 |

## 참고

- 브이월드 키는 저장소에 올리지 마세요 (스크립트는 환경변수로만 받습니다).
- 데이터를 공개 저장소에 올리기 전에 브이월드 이용약관을 한 번 확인해 주세요.
- 카카오 JS 키는 원래 공개되는 키라 `index.html`에 있어도 되지만, 도메인 등록으로 보호됩니다.
