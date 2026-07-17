from fastapi import APIRouter

from app.api.routes import auth, companies, health, opportunities, watchlist

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(opportunities.router, prefix="/opportunities", tags=["research"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
