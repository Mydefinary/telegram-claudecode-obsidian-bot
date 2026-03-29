# telegram-claudecode-obsidian-bot

텔레그램에 링크/메시지/이미지/txt 파일을 보내면 AI가 분석하여 옵시디언에 자동 저장하는 봇

> 분석 엔진으로 **Claude Code CLI**(구독 요금제), **Anthropic API**, **OpenAI API** 중 선택 가능합니다.
> 기본값은 `claude-cli`이며, `.env`의 `ANALYSIS_ENGINE`으로 변경합니다.

[English README](README.md)

## 주요 기능

- **URL 분석** -- 웹페이지 스크래핑 + AI 분석 후 옵시디언 노트 생성 (YouTube, Instagram, Threads 등 SNS 지원)
- **텍스트 분석** -- 텍스트를 AI가 정리하여 노트 생성
- **이미지 분석** -- 이미지를 AI가 읽고 분석, 원본 이미지는 vault에 첨부
- **txt 파일 일괄 처리** -- 파일 업로드 시 항목별로 큐 기반 병렬 처리 (동시 3개)
- **카카오톡 대화 파싱** -- 카카오톡 내보내기 txt를 자동 감지하여 메시지 단위로 분석
- **내용 중복 비교** -- 기존 노트와 내용을 비교하여 신규/중복/보강 판정
- **원본 저장** -- 분석 요약본과 함께 원본 콘텐츠를 접이식 callout으로 보관
- **6항목 노트 평가** -- 최신성/실용성/신뢰도/깊이/개발자적합성/클코적용성 (30점 만점, A~D 등급)
- **Claude Code 팁 4분기 처리** -- 팁 발견 시 텔레그램에서 Global 반영 / Skill 제작 / 팁 저장 / 스킵 선택
- **팁 풀 + 태그 매칭** -- 저장된 팁을 `/apply-tips`로 프로젝트에 태그 기반 매칭 적용
- **다국어 지원** -- 한국어/영어 출력 언어 선택 가능
- **다중 분석 엔진** -- Claude Code CLI, Anthropic API, OpenAI API 중 선택

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
   [analyzer.py] AI 분석 (Claude CLI / Anthropic API / OpenAI API)
        |
        v
   [obsidian_writer.py] 옵시디언 vault에 마크다운 저장 (원본 포함)
        |
        v
   [evaluator.py] 6항목 평가 + Claude Code 팁 추출
        |
        v
   [텔레그램 인라인 버튼] 팁 처리 4분기
        |
        +--[Global 반영]--> ~/.claude/CLAUDE.md
        +--[Skill 제작]---> ~/.claude/commands/{name}.md
        +--[팁 저장]------> ~/.claude/tips/{date}_{seq}.md (태그 포함)
        +--[스킵]---------> 옵시디언에만 보관
```

## 파일 구조

```
telegram-obsidian-bot/
├── bot.py                  # 메인 봇 (텔레그램 핸들러 + 큐 처리)
├── analyzer.py             # AI 분석 엔진 (Claude CLI / Anthropic / OpenAI)
├── scraper.py              # 웹페이지 스크래핑 (httpx + BeautifulSoup)
├── obsidian_writer.py      # 옵시디언 마크다운 저장 + 원본 보관 + 이미지 복사
├── evaluator.py            # 6항목 노트 평가 + Claude Code 팁 추출 + 팁 풀/스킬 생성
├── kakao_parser.py         # 카카오톡 대화 내보내기 txt 파싱
├── config.py               # 설정 (토큰, vault 경로, 분석 엔진)
├── prompts/                # 다국어 프롬프트 (ko.py, en.py)
│   ├── __init__.py
│   ├── ko.py
│   └── en.py
├── tests/                  # 테스트
│   ├── __init__.py
│   └── conftest.py
├── fix_existing_notes.py   # 기존 노트 일괄 정리 스크립트
├── backfill_originals.py   # 기존 노트 원본 소급 추가 스크립트
├── backfill_tags.py        # 기존 팁 태그 소급 생성 스크립트
├── Dockerfile              # Docker 이미지 빌드
├── docker-compose.yml      # Docker Compose 설정
├── start.bat               # Windows 서비스 실행용 배치 파일
├── requirements.txt        # 의존성
├── .env                    # 환경변수 (git 미추적)
└── .env.example            # 환경변수 예시
```

## 설치 및 실행

### 1. 사전 요구사항

- Python 3.10+
- 분석 엔진 중 하나:
  - [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) 설치 및 로그인 (기본값)
  - Anthropic API 키
  - OpenAI API 키

### 2. 의존성 설치

```bash
git clone https://github.com/YOUR_USERNAME/telegram-obsidian-bot.git
cd telegram-obsidian-bot
pip install -r requirements.txt
```

### 3. 환경변수 설정

`.env.example`을 복사하여 `.env` 파일을 생성하고 값을 채웁니다.

```bash
cp .env.example .env
```

| 변수 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | - | [BotFather](https://t.me/BotFather)에서 발급받은 텔레그램 봇 토큰 |
| `OBSIDIAN_VAULT_PATH` | Yes | - | 옵시디언 vault의 절대 경로 |
| `ANALYSIS_ENGINE` | No | `claude-cli` | 분석 엔진: `claude-cli`, `anthropic`, `openai` |
| `LANGUAGE` | No | `ko` | 출력 언어: `ko`, `en` |
| `MAX_CONCURRENT` | No | `3` | 동시 분석 작업 수 |
| `OBSIDIAN_FOLDER` | No | `텔레그램` | vault 내 저장 폴더명 |
| `ANTHROPIC_API_KEY` | 엔진이 `anthropic`일 때 | - | Anthropic API 키 |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-20250514` | Anthropic 모델명 |
| `OPENAI_API_KEY` | 엔진이 `openai`일 때 | - | OpenAI API 키 |
| `OPENAI_MODEL` | No | `gpt-4o` | OpenAI 모델명 |
| `CLAUDE_CMD` | No | 자동 감지 | Claude CLI 실행 경로 |

### 4. 실행

```bash
python bot.py
```

또는 Windows에서:

```bash
start.bat
```

### 5. Docker로 실행

```bash
docker compose up -d
```

### 6. 유틸리티 스크립트

```bash
python fix_existing_notes.py    # 기존 노트 frontmatter 일괄 정리
python backfill_originals.py    # 기존 URL 노트에 원본 소급 추가
python backfill_tags.py         # 기존 팁 파일에 태그 소급 생성
```

## 사용법

1. 텔레그램에서 봇과 대화를 시작합니다 (`/start`)
2. 아래 형식 중 하나를 보냅니다:
   - **URL** -- 웹페이지를 분석하여 노트 생성
   - **텍스트** -- 내용을 정리하여 노트 생성
   - **이미지** -- 이미지를 분석하여 노트 생성 (원본 첨부)
   - **txt 파일** -- 항목별로 분할하여 병렬 분석 (카카오톡 내보내기 자동 감지)
3. 분석 완료 후 옵시디언 vault의 저장 폴더에 마크다운 노트가 저장됩니다
4. Claude Code 팁이 발견되면 텔레그램에서 4개 버튼으로 처리:
   - **Global 반영** -- `~/.claude/CLAUDE.md`에 추가
   - **Skill 제작** -- `~/.claude/commands/`에 슬래시 커맨드 생성
   - **팁 저장** -- `~/.claude/tips/`에 태그와 함께 풀로 저장
   - **스킵** -- 옵시디언에만 보관
5. 프로젝트에서 `/apply-tips` 실행 시 팁 풀에서 태그 기반으로 적합한 팁을 추천

## 노트 평가 기준

| 항목 | 설명 | 1점 | 5점 |
|---|---|---|---|
| 최신성 | 현재 유효한 최신 정보인가 | 오래된 정보 | 최신 트렌드 |
| 실용성 | 실무에 바로 적용 가능한가 | 이론만 | 코드/워크플로우 포함 |
| 신뢰도 | 출처와 검증 수준 | 미검증/추측 | 공식 문서/전문가 |
| 깊이 | 인사이트 깊이 | 표면적 소개 | 심화 분석 |
| 개발자 적합성 | 개발자에게 유용한가 | 무관 | 핵심 실무 |
| 클코 적용성 | Claude Code 적용 가능 | 없음 | 바로 적용 가능 |

등급: **A**(25+) / **B**(19-24) / **C**(13-18) / **D**(12이하) (30점 만점)

## 기술 스택

| 구분 | 기술 |
|---|---|
| 언어 | Python 3.13 |
| 텔레그램 | python-telegram-bot |
| 웹 스크래핑 | httpx + BeautifulSoup4 |
| 분석 엔진 | Claude Code CLI / Anthropic API / OpenAI API (선택) |
| 환경변수 | python-dotenv |
| 노트 저장 | 옵시디언 vault에 직접 마크다운 파일 생성 |
| 컨테이너 | Docker + Docker Compose |

## 라이선스

MIT License
