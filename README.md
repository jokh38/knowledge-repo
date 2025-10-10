# Knowledge Repository

개인 지식 관리 시스템으로 웹 콘텐츠 수집, 요약, 의미론적 검색을 자동화합니다.

## 시스템 아키텍처

```
┌─────────────────┐
│  Mobile/Web UI  │
│  (URL Input)    │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────────────────────┐
│     FastAPI Server (GPU)        │
│  ┌──────────┐  ┌──────────────┐ │
│  │ /capture │  │   /query     │ │
│  └────┬─────┘  └──────┬───────┘ │
│       │                │         │
│  ┌────▼─────┐    ┌────▼──────┐  │
│  │Firecrawl │    │  RAG      │  │
│  │+ Ollama  │    │ Engine    │  │
│  └────┬─────┘    └────┬──────┘  │
└───────┼───────────────┼─────────┘
        │               │
        ▼               ▼
┌─────────────────────────────────┐
│     Obsidian Vault              │
│  00_Inbox/Clippings/*.md        │
│  + Vector Index (ChromaDB)      │
└─────────────────────────────────┘
```

## 주요 기능

- **웹 콘텐츠 수집**: URL에서 콘텐츠를 자동으로 스크랩하고 Markdown으로 변환
- **LLM 요약**: Qwen3-Coder-30B 모델을 사용하여 콘텐츠 자동 요약
- **Obsidian 통합**: 요약된 콘텐츠를 Obsidian vault에 자동 저장
- **의미론적 검색**: RAG(Retrieval Augmented Generation)를 사용한 지식 검색
- **웹 UI**: Gradio 기반의 사용자 친화적 인터페이스

## 시작하기

### 1. 환경 설정

```bash
# 가상 환경 생성
python -m venv venv
source venv/bin/activate  # Linux/WSL
# 또는 venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 복사하고 설정:

```bash
cp .env.example .env
```

`.env` 파일 설정:

```env
# Obsidian Vault 경로
OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault

# Ollama API 서버 (Qwen3-Coder-30B 모델)
OLLAMA_BASE_URL=http://10.243.15.166:8080

# ChromaDB 경로
CHROMA_DB_PATH=./chroma_db

# API 설정
API_HOST=0.0.0.0
API_PORT=8000
# No authentication needed for local runs
```

### 3. 서버 시작

#### API 서버

```bash
python main.py
```

#### 웹 UI

```bash
python ui.py
```

### 4. 초기 인덱싱

```bash
curl -X POST http://localhost:8000/reindex \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

## API 사용법

### URL 캡처

```bash
curl -X POST http://localhost:8000/capture \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'
```

### 지식 검색

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "기계 학습이란?", "top_k": 5}'
```

## 웹 인터페이스

- **URL 캡처**: `http://localhost:7860`
- **API 문서**: `http://localhost:8000/docs`
- **상태 확인**: `http://localhost:8000/health`

## 프로젝트 구조

```
knowledge-repo/
├── .env                    # 환경 변수
├── requirements.txt        # Python 의존성
├── main.py                # FastAPI 애플리케이션
├── scraper.py             # 웹 스크래핑 로직
├── summarizer.py          # LLM 요약
├── obsidian_writer.py     # Markdown 파일 작성기
├── retriever.py           # RAG 검색 엔진
├── ui.py                  # Gradio 웹 인터페이스
├── auth.py                # (optional; unused in local mode)
├── logging_config.py      # 로깅 설정
├── utils/
│   └── retry.py           # 재시도 데코레이터
├── chroma_db/             # 벡터 데이터베이스 (자생성)
├── logs/                  # 애플리케이션 로그
└── tests/                 # 테스트 파일
```

## 테스트

```bash
# 모든 테스트 실행
pytest tests/ -v

# 커버리지 보고서
pytest tests/ -v --cov=. --cov-report=html

# 특정 테스트 파일
pytest tests/test_scraper.py -v
```

## 개발

### 코드 스타일

```bash
# 코드 포맷팅
black *.py

# 린팅
flake8 *.py
```

### 로깅

로그는 `logs/` 디렉토리에 저장됩니다:

```bash
tail -f logs/knowledge_api.log
```

## 문제 해결

### 일반적인 문제

**Ollama 연결 시간 초과**
```bash
# Ollama 상태 확인
ollama list

# 타임아웃 증가
```

**GPU 메모리 부족**
```python
# CPU에서 임베딩 실행
Settings.embed_model = HuggingFaceEmbedding(
    model_name="...",
    device="cpu"
)
```

**ChromaDB 잠금 오류**
```bash
# 잠금 파일 제거
rm -rf chroma_db/chroma.sqlite3-wal
rm -rf chroma_db/chroma.sqlite3-shm
```

## 라이선스

MIT License

## 기여

기여는 환영합니다! 이슈를 제거하거나 풀 리퀘스트를 보내주세요.

## 변경 로그

### v1.0.0 (2025-10-08)
- 초기 릴리스
- 웹 콘텐츠 수집 및 요약
- RAG 기반 검색
- Obsidian 통합
- 웹 UI