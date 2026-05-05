"""灵犀·校园 — QwenPaw 灵魂后端入口"""

if __name__ == "__main__":
    import uvicorn
    from lingxi_qwenpaw.api import app

    print("=" * 50)
    print("灵犀·校园 启动中...")
    print(f"LLM: {__import__('lingxi_qwenpaw.config', fromlist=['LLM_MODEL']).LLM_MODEL}")
    print("=" * 50)

    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="info")
