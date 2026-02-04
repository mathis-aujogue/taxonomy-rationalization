.PHONY: db api frontend

#install dependencies
install:
	cd backend && uv sync
	cd frontend && npm install

#step 1, open a terminal and run postgres db (docker needs to be running)
db:
	docker-compose up 

#step 2, in another terminal, run the api
api:
	cd backend && uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

#step 3, in another terminal, run the frontend, then access http://localhost:5173
frontend:
	cd frontend && npm run dev
