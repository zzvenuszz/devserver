name: Sync to Hugging Face
on:
  push:
    branches: [main]

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
        with:
          fetch-depth: 0

      - name: Push to Hugging Face
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: |
          # Xóa remote hf cũ nếu có
          git remote remove hf || true
          # Thêm remote hf với Token được chèn trực tiếp vào URL
          git remote add hf https://noobsclan101:${HF_TOKEN}@huggingface.co/spaces/noobsclan101/devserver
          # Push code
          git push hf main --force