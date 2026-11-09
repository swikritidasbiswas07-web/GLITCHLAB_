/// <reference types="vite/client" />
const KEY = 'glitchlab_session_token';
export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const getToken = () => sessionStorage.getItem(KEY);
export const saveToken = (token: string) => sessionStorage.setItem(KEY, token);
export const clearToken = () => sessionStorage.removeItem(KEY);
export function authHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return headers;
}
export async function authFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(input, { ...init, headers: authHeaders(init.headers) });
  if (response.status === 401 && getToken()) {
    clearToken();
    window.dispatchEvent(new Event('glitchlab-session-expired'));
  }
  return response;
}
