import api from './api';

export async function getImpactSummary() {
  const { data } = await api.get('/impact/summary/');
  return data;
}
