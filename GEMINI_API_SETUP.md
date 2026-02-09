# Gemini API Setup Guide

## ✅ API Key Đã Được Cấu Hình

API Key đã được cập nhật trong code:
- **API Key**: `AIzaSyAgAZu1kmuu8WhlIaWK7PlPHUVwDiMhaKc`
- **Model**: `gemini-1.5-pro` (gemini-3-pro chưa có sẵn)
- **Location**: `config.py` và `gemini_service.py`

## 📦 Installation

### 1. Install Google Generative AI Library

```bash
pip install google-generativeai>=0.3.0
```

Hoặc cài đặt tất cả dependencies:

```bash
pip install -r requirements.txt
```

### 2. Verify Installation

```python
import google.generativeai as genai
print("✓ Google Generative AI installed successfully")
```

## 🔧 Configuration

### Option 1: Use Default API Key (Đã cấu hình sẵn)

API key đã được hardcode trong `config.py`, app sẽ tự động sử dụng.

### Option 2: Environment Variable (Khuyến nghị cho production)

```bash
export GEMINI_API_KEY="AIzaSyAgAZu1kmuu8WhlIaWK7PlPHUVwDiMhaKc"
```

Hoặc trong `.env` file:
```
GEMINI_API_KEY=AIzaSyAgAZu1kmuu8WhlIaWK7PlPHUVwDiMhaKc
```

### Option 3: Pass as Parameter

```python
from gemini_service import GeminiService

service = GeminiService(api_key="AIzaSyAgAZu1kmuu8WhlIaWK7PlPHUVwDiMhaKc")
```

## 🚀 Usage

App sẽ tự động:
1. ✅ Kiểm tra xem `google-generativeai` đã được cài đặt chưa
2. ✅ Load API key từ config hoặc environment
3. ✅ Initialize Gemini model
4. ✅ Fallback về mock responses nếu có lỗi

## 🔍 Testing

### Test API Connection

```python
from gemini_service import GeminiService

service = GeminiService()
response = service._call_gemini(
    "Hello, can you help me?",
    "You are a helpful assistant."
)
print(response)
```

### Test Normalization

```python
import pandas as pd
from gemini_service import GeminiService

service = GeminiService()
nodes = pd.DataFrame({'node_id': [1, 2], 'name': ['A', 'B']})
edges = pd.DataFrame({'from_node': [1], 'to_node': [2], 'mode': ['road']})
demand = pd.DataFrame({'origin': [1], 'destination': [2], 'volume': [100]})

result = service.normalize_data(nodes, edges, demand)
print(result)
```

## ⚠️ Troubleshooting

### Issue: "google-generativeai not installed"
**Solution**: 
```bash
pip install google-generativeai
```

### Issue: "Failed to initialize Gemini API"
**Solution**: 
- Kiểm tra API key có đúng không
- Kiểm tra internet connection
- Kiểm tra API quota/limits

### Issue: "Using mock responses"
**Solution**: 
- App sẽ tự động fallback về mock responses nếu API không available
- Kiểm tra console logs để xem lỗi cụ thể

## 📝 Notes

- **Model**: Hiện tại sử dụng `gemini-1.5-pro` vì `gemini-3-pro` chưa có sẵn
- **Fallback**: App tự động fallback về mock responses nếu API không available
- **Error Handling**: Tất cả errors được catch và log, không làm crash app

## 🔐 Security

⚠️ **Lưu ý**: API key hiện tại được hardcode trong code. Cho production:
- Sử dụng environment variables
- Không commit API key vào git
- Sử dụng secrets management (AWS Secrets Manager, etc.)

## ✅ Status

- ✅ API key đã được cấu hình
- ✅ Code đã được cập nhật để sử dụng real API
- ✅ Fallback mechanism đã được implement
- ✅ Error handling đã được thêm vào
