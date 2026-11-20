const baseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
async function request(path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed. Check your input.');
  return data;
}
export const getHealth = signal => request('/api/health', { signal });
export const getModel = signal => request('/api/model', { signal });
export const predictCSV = file => request('/api/predict/csv', { method: 'POST', headers: { 'Content-Type': 'text/csv' }, body: file });
