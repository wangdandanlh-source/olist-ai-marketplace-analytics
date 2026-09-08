"""Create local-only directories; never downloads data."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name in ['data/raw/brazilian-ecommerce','data/raw/marketing-funnel-olist','data/interim','data/processed','docs','outputs']:
    (ROOT/name).mkdir(parents=True,exist_ok=True)
print('Local directories ready. Obtain source files separately; see analysis/README.md.')
