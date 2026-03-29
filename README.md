# telegram-obsidian-bot

텔레그램에 링크/메시지/이미지/txt 파일을 보내면 Claude Code CLI가 분석하여 옵시디언에 자동 저장하는 봇

> Claude Code CLI를 사용하므로 별도의 Anthropic API 키가 필요 없습니다. Claude Code 구독 요금제 내에서 동작합니다.

## 주요 기능

- **URL 분석** -- 웹페이지 스크래핑 + Claude 분석 후 옵시디언 노트 생성 (YouTube, Instagram, Threads 등 SNS 지원)
- **텍스트 분석** -- 텍스트를 Claude가 정리하여 노트 생성
- **이미지 분석** -- 이미지를 Claude가 읽고 분석, 원본 이미지는 vault에 첨부
- **txt 파일 일괄 처리** -- 파일 업로드 시 항목별로 큐 기반 병렬 처리 (동시 3개)
- **카카오톡 대화 파싱** -- 카카오톡 내보내기 txt를 자동 감지하여 메시지 단위로 분석
- **내용 중복 비교** -- 기존 노트와 내용을 비교하여 신규/중복/보강 판정
- **노트 평가** -- 저장 후 자동 등급 평가 (A~D) + Claude Code 팁 발견 시 텔레그램에서 승인 후 적용

## 아키텍처

```
텔레그램 메시지/파일
        |
        v
   [bot.py] 텔레그램 핸들러 + 큐 처리
        |
        v
   [scraper.py] 웹페이지 스크래핑 (URL인 경우)
        |
        v
   [analyzer.py] Claude Code CLI 호출 (stdin 파이프)
   claude -p - --allowedTools "WebFetch,WebSearch,Read"
        |
        v
   [obsidian_writer.py] 옵시디언 vault에 마크다운 저장
        |
        v
   [evaluator.py] 노트 품질 평가 + Claude Code 팁 추출
```

## 파일 구조

```
telegram-obsidian-bot/
├── bot.py                # 메인 봇 (텔레그램 핸들러 + 큐 처리)
├── analyzer.py           # Claude Code CLI 호출하여 분석
├── scraper.py            # 웹페이지 스크래핑 (httpx + BeautifulSoup)
├── obsidian_writer.py    # 옵시디언 마크다운 저장 + 이미지 복사
├── evaluator.py          # 노트 평가 + Claude Code 팁 자동 적용
├── kakao_parser.py       # 카카오톡 대화 내보내기 txt 파싱
├── config.py             # 설정 (토큰, vault 경로)
├── fix_existing_notes.py # 기존 노트 일괄 정리 스크립트
├── requirements.txt      # 의존성
├── .env                  # 환경변수 (git 미추적)
└── .env.example          # 환경변수 예시
```

## 설치 및 실행

### 1. 사전 요구사항

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) 설치 및 로그인 완료 (구독 요금제)

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 환경변수 설정

`.env.example`을 복사하여 `.env` 파일을 생성하고 값을 채웁니다.

```bash
cp .env.example .env
```

`.env` 내용:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OBSIDIAN_VAULT_PATH=E:/옵시디언/호아1
```

| 변수 | 설명 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | [BotFather](https://t.me/BotFather)에서 발급받은 텔레그램 봇 토큰 |
| `OBSIDIAN_VAULT_PATH` | 옵시디언 vault의 절대 경로 |

### 4. 실행

```bash
python bot.py
```

기존 노트 일괄 정리 (선택):

```bash
python fix_existing_notes.py
```

## 사용법

1. 텔레그램에서 봇과 대화를 시작합니다 (`/start`)
2. 아래 형식 중 하나를 보냅니다:
   - **URL** -- 웹페이지를 분석하여 노트 생성
   - **텍스트** -- 내용을 정리하여 노트 생성
   - **이미지** -- 이미지를 분석하여 노트 생성 (원본 첨부)
   - **txt 파일** -- 항목별로 분할하여 병렬 분석 (카카오톡 내보내기 자동 감지)
3. 분석 완료 후 옵시디언 vault의 `텔레그램/` 폴더에 마크다운 노트가 저장됩니다
4. Claude Code 팁이 발견되면 텔레그램에서 적용/스킵 버튼으로 승인할 수 있습니다

## 기술 스택

| 구분 | 기술 |
|---|---|
| 언어 | Python 3.13 |
| 텔레그램 | python-telegram-bot |
| 웹 스크래핑 | httpx + BeautifulSoup4 |
| 분석 엔진 | Claude Code CLI (`claude -p -`, 구독 요금제 -- API 키 불필요) |
| 환경변수 | python-dotenv |
| 노트 저장 | 옵시디언 vault에 직접 마크다운 파일 생성 |
