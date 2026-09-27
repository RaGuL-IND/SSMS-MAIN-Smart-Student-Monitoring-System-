# Frontend Setup

This folder contains a lightweight Vite React + TypeScript app for the SSMS login page.

## Setup

1. Open a terminal in `Frontend/`
2. Run `npm install`
3. Run `npm run dev`

## Notes

- The app proxies `/api` to `http://localhost:5000`
- The backend must be running separately on port `5000`
- The sample login page sends credentials to `/api/auth/login`
