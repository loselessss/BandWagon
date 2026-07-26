# BandWagon 개발 지침

## 버전 규칙

릴리스 버전은 `x.y.z` 형식을 사용한다.

- `x`: 호환성이 깨지는 메이저 업데이트
- `y`: 하위 호환되는 새 기능 추가
- `z`: 하위 호환되는 버그 수정

상위 자리를 올리면 오른쪽 자리는 0으로 초기화한다. 여러 종류의 변경을
한 릴리스에 함께 배포하면 가장 높은 단계에 맞춘다.

버전을 올릴 때 다음 파일을 항상 함께 갱신한다.

- `bandwagon/meta.py`: `APP_VERSION`, `RELEASE_DATE`
- `installer.iss`: `MyAppVersion`
- `CHANGELOG.md`: 최신 패치노트를 맨 위에 추가

## 검증

- 변경 후 `python -m unittest discover -s tests -v`를 실행한다.
- 커밋 전 `git diff --check`로 공백 오류를 확인한다.
