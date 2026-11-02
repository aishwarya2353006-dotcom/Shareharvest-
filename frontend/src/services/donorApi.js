import api from './api';

async function getAllPages(path, params = {}) {
  const items = [];
  let page = 1;
  let hasNext = true;

  while (hasNext) {
    const response = await api.get(path, { params: { ...params, page } });
    const payload = response.data;
    if (Array.isArray(payload)) {
      items.push(...payload);
      hasNext = false;
    } else {
      items.push(...(payload.results || []));
      hasNext = Boolean(payload.next);
      page += 1;
    }
  }

  return items;
}

export const getDonorDonations = () => getAllPages('/donations/donations/', { mine: 'true' });

export const getDonorOrganizations = () => getAllPages('/organizations/organizations/');

export async function getRequestsForDonations(donations) {
  const results = [];
  // Keep the number of concurrent queries bounded while honoring the API's single-donation filter.
  for (let index = 0; index < donations.length; index += 5) {
    const batch = donations.slice(index, index + 5);
    const responses = await Promise.all(batch.map(donation =>
      getAllPages('/donation-requests/', { donation: donation.id })
    ));
    results.push(...responses.flat());
  }
  return results;
}

export const createDonation = payload => api.post('/donations/donations/', payload);
export const updateDonation = (id, payload) => api.patch(`/donations/donations/${id}/`, payload);
export const approveDonationRequest = (id, payload, idempotencyKey) => api.post(
  `/donation-requests/${id}/approve/`, payload, { headers: { 'Idempotency-Key': idempotencyKey } }
);
export const rejectDonationRequest = id => api.post(`/donation-requests/${id}/reject/`, {});

export function getApiErrorMessage(error) {
  const data = error?.response?.data;
  if (typeof data === 'string') return data;
  if (data?.detail) return data.detail;
  if (data && typeof data === 'object') {
    return Object.entries(data)
      .map(([field, messages]) => {
        const readableField = field.replaceAll('_', ' ');
        const readableMessages = Array.isArray(messages) ? messages.join(' ') : String(messages);
        return `${readableField}: ${readableMessages}`;
      })
      .join(' ');
  }
  return error?.message || 'Something went wrong. Please try again.';
}

export const QUANTITY_UNITS = [
  { value: 'kg', label: 'kg', dimension: 'mass', factor: 1000 },
  { value: 'g', label: 'g', dimension: 'mass', factor: 1 },
  { value: 'l', label: 'L', dimension: 'volume', factor: 1000 },
  { value: 'ml', label: 'mL', dimension: 'volume', factor: 1 },
  { value: 'units', label: 'units', dimension: 'count:units', factor: 1 },
  { value: 'boxes', label: 'boxes', dimension: 'count:boxes', factor: 1 },
  { value: 'trays', label: 'trays', dimension: 'count:trays', factor: 1 },
];

export const getUnit = value => QUANTITY_UNITS.find(unit => unit.value === value);

export function quantityInBase(quantity, unitValue) {
  const unit = getUnit(unitValue);
  return unit ? Number(quantity) * unit.factor : NaN;
}

export function fromBaseQuantity(quantity, unitValue) {
  const unit = getUnit(unitValue);
  return unit ? Number(quantity) / unit.factor : NaN;
}
