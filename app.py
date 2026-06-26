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

      - name: Configure Git
        run: |
          git config --global user.email "action@github.com"
          git config --global user.name "GitHub Action"

      - name: Push to Hugging Face
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: |
          git remote add hf https://noobsclan101:$HF_TOKEN@huggingface.co/spaces/noobsclan101/devserver
          git push hf main --force