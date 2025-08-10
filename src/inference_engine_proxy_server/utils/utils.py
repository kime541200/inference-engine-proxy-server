from typing import Optional, Literal
import shutil
import httpx
import requests
import importlib.util
from urllib.parse import urljoin
from rich import print as rprint

__all__ = ["a_get_model_name", "a_check_provider"]

def check_required_packages(*package_names: str) -> None:
    """Check if required Python packages are installed.

    This function verifies that all specified packages are available in the current Python environment.
    If any package is not found, it raises an ImportError with instructions to install the missing package.

    Args:
        *package_names: Variable length argument list of package names to check.

    Raises:
        ImportError: If any of the specified packages is not installed in the environment.
            The error message includes the name of the missing package and instructions to install it
            using pip.

    Example:
        >>> check_required_packages('requests', 'numpy')
        # If 'requests' is not installed:
        # ImportError: The required package 'requests' is not installed.
        # Please install it by running:
        #
        #     pip install requests
    """
    for package in package_names:
        if importlib.util.find_spec(package) is None:
            raise ImportError(
                f"The required package '{package}' is not installed.\n"
                f"Please install it by running:\n\n    pip install {package}"
            )

# ==================== Beauty print ====================

def print_centered_text(text: str, padding_char=' '):
    """
    在終端機中將文字水平置中並打印出來。

    Args:
        text (str): 要打印的文字。
        padding_char (str, optional): 用於填充的字符。預設為空格。

    Returns:
        None
    """
    # 取得終端機視窗尺寸
    terminal_width = shutil.get_terminal_size().columns
    # 計算讓印出文字"水平置中"所需的空格數
    padding = (terminal_width - len(text)) // 2
    # 印出"水平置中"的文字
    print(padding_char * max(padding, 0) + text + padding_char * max(padding, 0))


def print_detail(context, title: str = "", padding: str = "=", start_index: Optional[int] = None, end_index: Optional[int] = None, is_convo: bool = False):
    """
    打印詳細內容，可選擇顯示清單或對話，並在上下加上置中的標題與邊框。

    根據 `context` 的型別決定打印方式：
    - 如果是一般清單，可指定顯示的範圍（start_index 到 end_index）。
    - 如果是對話清單（清單中包含 dict，且有 'role' 和 'content'），會以對話形式顯示。
    - 若為其他資料型別，則直接以 rich 格式打印。

    Args:
        context (Any): 要打印的內容，可為清單（list）、對話清單（list of dict），或其他類型。
        title (str, optional): 置中顯示的標題文字，預設為空字串。
        padding (str, optional): 標題與底部分隔線用的填充字元，預設為 '='。
        start_index (Optional[int], optional): 要顯示清單的起始索引，預設為 None（從頭開始）。
        end_index (Optional[int], optional): 要顯示清單的結束索引，預設為 None（顯示到尾）。
        is_convo (bool, optional): 若設為 True，將清單內容視為對話並用對話格式打印，預設為 False。

    Returns:
        None
    """
    # Helper function to print list-type contexts.
    def _print_list(lst: list, start_index: Optional[int] = None, end_index: Optional[int] = None, is_convo: bool = False):
        total_len = len(lst)
        start = start_index if start_index is not None else 0
        end = end_index if end_index is not None else total_len
        sliced = lst[start:end]

        if start > 0:
            print(f"... ({start} items before)")

        if is_convo:
            _print_convo(sliced)
        else:
            rprint(sliced)

        if end < total_len:
            print(f"... ({total_len - end} items more)")

    # Helper function to print a conversation (list of dict items with "role" and "content").
    def _print_convo(convo: list):
        for c in convo:
            # Using single quotes outside so that inner double quotes work correctly.
            print(f'{c["role"]}>>> {c["content"]}\n')

    # Prepare and print header with the centered title.
    title_str = f" {title} " if title else ""
    print()
    print_centered_text(text=title_str, padding_char=padding)

    # Determine how to print the context depending on its type.
    if isinstance(context, list):
        _print_list(context, start_index, end_index, is_convo)
    else:
        rprint(context)

    # Print a footer border.
    print_centered_text(text="", padding_char=padding)
    print()

# ======================================================

# ==================== LLM API ====================

async def a_get_model_name(base_url: str, index: int = 0) -> str:
    url = urljoin(base_url, "/v1/models")
    from ..core.http_client import get_client   # 使用全域的 httpx.AsyncClient 實例，避免每次請求都創建新的連接
    client = get_client()
    data = (await client.get(url)).json()
    return data["data"][index]["id"]

async def a_check_provider(base_url: str, model: str) -> str:
    url = urljoin(base_url, "/v1/models")
    from ..core.http_client import get_client   # 使用全域的 httpx.AsyncClient 實例，避免每次請求都創建新的連接
    client = get_client()
    data = (await client.get(url)).json()
    for entry in data["data"]:
        if entry.get("id") == model:
            return entry.get("owned_by")          # 'llamacpp' or 'vllm'
    raise ValueError(f"model {model} not found at {base_url}")

def get_model_name(base_url: str, index: int = 0) -> str:
    try:
        url = urljoin(base_url, "/v1/models")
        response = requests.get(url).json()
        return response["data"][index]["id"]
    except Exception as e:
        raise Exception(f"Get model name error: {e}")


def check_provider(base_url: str, model: str) -> Literal['vllm', 'llamacpp']:
    try:
        headers = {"Content-Type": "application/json"}
        url = urljoin(base_url, '/v1/models')
        response = requests.get(url, headers=headers)
        
        for res in response.json()["data"]:
            if res.get("id") and res.get("id") == model:
                return res.get("owned_by")
        
        raise Exception(f"Can't find matched model name: {model} from provided URL({base_url})")
    except Exception as e:
        raise Exception(f"Get model provider error: {e}")


def check_context_window(base_url: str, model: str) -> int:
    try:
        headers = {"Content-Type": "application/json"}
        provider = check_provider(base_url, model)

        if provider == "vllm":
            url = urljoin(base_url, "/v1/models")
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            data = response.json().get("data", [])
            for res in data:
                if res.get("id") == model:
                    max_len = res.get("max_model_len")
                    if max_len is not None:
                        return max_len
                    else:
                        raise Exception(f"Model {model} found but 'max_model_len' is missing.")
            
            raise Exception(f"Model {model} not found in /v1/models response.")

        elif provider == "llamacpp":
            url = urljoin(base_url, "/props")
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            ctx = response.json().get("default_generation_settings", {}).get("n_ctx")
            if ctx is not None:
                return ctx
            else:
                raise Exception(f"'n_ctx' not found in default_generation_settings.")

        else:
            raise Exception(f"Unsupported provider type: {provider}")

    except Exception as e:
        raise Exception(f"Check context window error: {e}")


def count_token(content: str, token_counter_url: Optional[str]) -> int:
    """
    Count the number of tokens in a given text using either a local tokenizer (tiktoken)
    or an external token counting API (based on the provider: llamacpp or vllm).

    Args:
        content (str): The input string whose tokens are to be counted.
        token_counter_url (Optional[str]): URL of the token counting service. 
            If None, local counting will be used via `tiktoken`.

    Raises:
        ImportError: If `tiktoken` is not installed when local tokenization is required.
        Exception: If tokenization fails due to API error or invalid provider.

    Returns:
        int: The number of tokens in the input string.
    """
    try:
        if not token_counter_url:
            try:
                check_required_packages("tiktoken")
                import tiktoken
                tokenizer = tiktoken.get_encoding('cl100k_base')
                return len(tokenizer.encode(content, allowed_special="all"))
            except ImportError as e:
                raise ImportError(f"tiktoken is required for local token counting but is not installed: {e}")
            except Exception as e:
                raise Exception(f"Error during local token counting: {e}")
        else:
            try:
                headers = {"Content-Type": "application/json"}
                
                model_name = get_model_name(token_counter_url)
                provider = check_provider(token_counter_url, model_name)
                

                url = urljoin(token_counter_url, '/tokenize')

                if provider == 'llamacpp':
                    payload = {"content": content}
                    response = requests.post(url=url, headers=headers, json=payload)
                    response.raise_for_status()
                    return len(response.json()["tokens"])

                elif provider == 'vllm':
                    payload = {"prompt": content, "model": model_name}
                    response = requests.post(url=url, headers=headers, json=payload)
                    response.raise_for_status()
                    return response.json()["count"]

                else:
                    raise Exception(f"Invalid LLM provider: {provider}")
            except requests.RequestException as e:
                raise Exception(f"Failed to call token counter API: {e}")
            except KeyError as e:
                raise Exception(f"Missing expected field in API response: {e}")
            except Exception as e:
                raise Exception(f"Error during remote token counting: {e}")
    except Exception as final_error:
        raise final_error
    
# =================================================