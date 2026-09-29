.PHONY: all db test model analysis app notebooks

all: db test model analysis app

db:
	python src/build_db.py

test:
	python -m pytest -q tests

model:
	python src/model.py

analysis:
	cd src && python analysis.py

app:
	cd src && python build_app.py

notebooks:
	cd notebooks && for nb in *.ipynb; do jupyter nbconvert --to notebook --execute --inplace "$$nb"; done
