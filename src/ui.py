import gradio as gr
import requests
import os
import logging
import time
from typing import Tuple, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
# No authentication in local mode

def processing_status_generator():
    """Generate processing status messages for URL capture"""
    status_messages = [
        "🔄 URL 스크래핑 시작...",
        "📄 콘텐츠 분석 중...",
        "🤖 LLM 요약 생성 중...",
        "💾 Obsidian 저장 중...",
        "📚 벡터 인덱싱 중...",
        "✨ 최종 처리 중..."
    ]

    for i, message in enumerate(status_messages):
        yield f"⏳ 처리 중: {message}"
        time.sleep(2)  # Simulate processing time for demo

    yield "🎉 처리 완료!"

def capture_url_ui(url: str, method: str = "auto") -> str:
    """Gradio interface for URL capture"""
    try:
        headers = {}

        payload = {"url": url}
        if method != "auto":
            payload["method"] = method

        response = requests.post(
            f"{API_BASE_URL}/capture",
            json=payload,
            headers=headers,
            timeout=120  # Increased timeout for LLM processing
        )

        if response.status_code == 200:
            result = response.json()
            return f"✅ 저장 완료!\n파일: {result['file_path']}\n제목: {result['title']}"
        else:
            error_msg = response.json().get("detail", "Unknown error")
            return f"❌ 오류: {error_msg}"
    except requests.exceptions.Timeout:
        return "❌ 오류: 요청 시간 초과 (LLM 처리는 최대 2분까지 소요될 수 있습니다)"
    except requests.exceptions.ConnectionError:
        return f"❌ 오류: API 서버에 연결할 수 없습니다 ({API_BASE_URL})"
    except Exception as e:
        return f"❌ 오류: {str(e)}"

def query_knowledge_ui(query: str, top_k: int = 5) -> Tuple[str, str]:
    """Gradio interface for knowledge query"""
    try:
        headers = {}

        payload = {"query": query, "top_k": top_k}

        response = requests.post(
            f"{API_BASE_URL}/query",
            json=payload,
            headers=headers,
            timeout=60  # Increased timeout for LLM processing
        )

        if response.status_code == 200:
            result = response.json()

            # Format answer
            answer = f"## 답변\n\n{result['answer']}"

            # Format sources
            sources = "## 출처\n\n"
            for i, source in enumerate(result['sources'], 1):
                sources += f"{i}. **{source['file_path']}**\n"
                if source.get('score'):
                    sources += f"   - 유사도: {source['score']:.3f}\n"
                sources += f"   - 내용: {source['content_preview']}\n\n"

            return answer, sources
        else:
            error_msg = response.json().get("detail", "Unknown error")
            return f"❌ 오류: {error_msg}", ""
    except requests.exceptions.Timeout:
        return "❌ 오류: 요청 시간 초과 (LLM 처리는 최대 1분까지 소요될 수 있습니다)", ""
    except requests.exceptions.ConnectionError:
        return f"❌ 오류: API 서버에 연결할 수 없습니다 ({API_BASE_URL})", ""
    except Exception as e:
        return f"❌ 오류: {str(e)}", ""

def reindex_vault_ui(force: bool = False) -> str:
    """Gradio interface for vault reindexing"""
    try:
        headers = {}
        
        payload = {"force": force}

        
        response = requests.post(
            f"{API_BASE_URL}/reindex",
            json=payload,
            headers=headers,
            timeout=300  # Longer timeout for reindexing
        )
        
        if response.status_code == 200:
            return "✅ 재인덱싱 완료!"
        else:
            error_msg = response.json().get("detail", "Unknown error")
            return f"❌ 오류: {error_msg}"
    except requests.exceptions.Timeout:
        return "❌ 오류: 재인덱싱 시간 초과 (5분)"
    except requests.exceptions.ConnectionError:
        return f"❌ 오류: API 서버에 연결할 수 없습니다 ({API_BASE_URL})"
    except Exception as e:
        return f"❌ 오류: {str(e)}"

def get_health_status() -> str:
    """Get API health status"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            return f"✅ API 상태: {health['status']}\nOllama: {health['ollama']}\nVault: {health['vault_path']}"
        else:
            return "❌ API 상태 확인 실패"
    except Exception as e:
        return f"❌ API 연결 오류: {str(e)}"

# Create Gradio interface
with gr.Blocks(title="지식 저장소") as iface:
    gr.Markdown("# 📚 지식 저장소")
    gr.Markdown("웹 페이지를 요약하여 Obsidian에 저장하고 의미론적 검색을 수행합니다.")
    
    with gr.Tabs():
        # URL Capture Tab
        with gr.TabItem("URL 캡처"):
            gr.Markdown("## 웹 페이지 캡처")
            gr.Markdown("⚠️ **참고**: LLM 요약 처리는 최대 1-2분 정도 소요될 수 있습니다.")
            
            with gr.Row():
                url_input = gr.Textbox(
                    label="URL", 
                    placeholder="https://example.com/article",
                    scale=4
                )
                method_dropdown = gr.Dropdown(
                    choices=["auto", "bash", "python"],
                    value="auto",
                    label="스크래핑 방법",
                    scale=1
                )
            
            capture_btn = gr.Button("캡처", variant="primary")
            capture_output = gr.Textbox(label="결과", lines=5)

            capture_btn.click(
                fn=capture_url_ui,
                inputs=[url_input, method_dropdown],
                outputs=capture_output,
                show_progress=True  # Show progress during processing
            )
        
        # Knowledge Query Tab
        with gr.TabItem("지식 검색"):
            gr.Markdown("## 저장된 지식 검색")
            
            with gr.Row():
                query_input = gr.Textbox(
                    label="검색어", 
                    placeholder="검색할 내용을 입력하세요...",
                    scale=3
                )
                top_k_slider = gr.Slider(
                    minimum=1,
                    maximum=10,
                    value=5,
                    step=1,
                    label="검색 결과 수",
                    scale=1
                )
            
            query_btn = gr.Button("검색", variant="primary")

            with gr.Row():
                answer_output = gr.Markdown(label="답변")
                sources_output = gr.Markdown(label="출처")

            query_btn.click(
                fn=query_knowledge_ui,
                inputs=[query_input, top_k_slider],
                outputs=[answer_output, sources_output],
                show_progress=True  # Show progress during processing
            )
        
        # Management Tab
        with gr.TabItem("관리"):
            gr.Markdown("## 시스템 관리")
            
            with gr.Row():
                health_btn = gr.Button("상태 확인")
                health_output = gr.Textbox(label="시스템 상태", lines=3)
                
                health_btn.click(
                    fn=get_health_status,
                    outputs=health_output
                )
            
            gr.Markdown("### 재인덱싱")
            gr.Markdown("Obsidian vault의 모든 파일을 다시 인덱싱합니다.")
            
            with gr.Row():
                force_checkbox = gr.Checkbox(label="기존 인덱스 삭제 후 재인덱싱")
                reindex_btn = gr.Button("재인덱싱 시작", variant="secondary")
                reindex_output = gr.Textbox(label="재인덱싱 결과")
                
                reindex_btn.click(
                    fn=reindex_vault_ui,
                    inputs=[force_checkbox],
                    outputs=reindex_output
                )
    
    # Footer
    gr.Markdown("---")
    gr.Markdown(f"API 서버: {API_BASE_URL}")

# Run on all interfaces to access from mobile
if __name__ == "__main__":
    import socket

    server_name = "0.0.0.0"
    server_port = 7860

    # Check if port is already in use and find available port if needed
    def find_available_port(start_port):
        """Find an available port starting from start_port"""
        for port_num in range(start_port, start_port + 10):  # Try 10 ports
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)
                    result = sock.connect_ex((server_name, port_num))
                    if result != 0:  # Port is available
                        return port_num
            except Exception:
                continue
        raise RuntimeError(f"No available ports found in range {start_port}-{start_port + 9}")

    try:
        # Try to launch with configured port first
        logger.info(f"Starting Gradio UI on {server_name}:{server_port}")
        iface.launch(
            server_name=server_name,
            server_port=server_port,
            share=False  # Set to True to create public link
        )
    except OSError as e:
        if "Address already in use" in str(e):
            logger.warning(f"Port {server_port} is already in use, finding available port...")
            available_port = find_available_port(server_port + 1)
            logger.info(f"Starting Gradio UI on {server_name}:{available_port}")
            iface.launch(
                server_name=server_name,
                server_port=available_port,
                share=False
            )
        else:
            raise