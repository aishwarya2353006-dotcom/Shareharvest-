import api from './api';

async function getAllPages(path, params = {}) {
  const items = [];
  let page = 1;
  let hasNext = true;
  while (hasNext) {
    const { data } = await api.get(path, { params: { ...params, page } });
    if (Array.isArray(data)) {
      items.push(...data);
      hasNext = false;
    } else {
      items.push(...(data.results || []));
      hasNext = Boolean(data.next);
      page += 1;
    }
  }
  return items;
}

export const getAvailableDonations = () => getAllPages('/donations/donations/', { browse: 'true' });
export const getRecipientOrganizations = () => getAllPages('/organizations/organizations/');
export const getMyDonationRequests = () => getAllPages('/donation-requests/', { mine: 'true' });
export const createDonationRequest = payload => api.post('/donation-requests/', payload);
