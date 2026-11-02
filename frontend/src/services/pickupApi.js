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

export const getPickups = () => getAllPages('/pickups/');
export const getEligibleAllocations = () => getAllPages('/pickups/eligible-allocations/');
export const getAvailableVolunteers = allocationId => api.get(
  '/pickups/available-volunteers/',
  { params: { allocation: allocationId } },
).then(response => response.data);
export const createPickup = payload => api.post('/pickups/', payload);
export const updatePickup = (id, payload) => api.patch(`/pickups/${id}/`, payload);
export const assignPickupVolunteer = (id, volunteer) => api.post(
  `/pickups/${id}/assign-volunteer/`,
  { volunteer },
);
export const startPickup = id => api.post(`/pickups/${id}/start/`, {});
export const completePickup = (id, payload) => api.post(
  `/pickups/${id}/complete/`,
  payload,
);
export const failPickup = (id, failureReason) => api.post(
  `/pickups/${id}/fail/`,
  { failure_reason: failureReason },
);
export const markPickupNoShow = id => api.post(`/pickups/${id}/no-show/`, {});
export const cancelPickup = id => api.post(`/pickups/${id}/cancel/`, {});
