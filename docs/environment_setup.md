# Environment Setup

## 1. Clone Repository

git clone https://github.com/FredrickMbithi/fx-quant-research
cd fx-quant-research

## 2. Create Virtual Environment

python3 -m venv venv
source venv/bin/activate

## 3. Install Dependencies

pip install -r requirements.txt

## 4. Verify Environment

python src/utils/environment.py

Expected:
Prints Python and library versions.
