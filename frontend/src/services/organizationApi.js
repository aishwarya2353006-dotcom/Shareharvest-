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

export const getOrganizations = () => getAllPages('/organizations/organizations/');
export const getMyMemberships = () => getAllPages('/organizations/memberships/');
export const getOrganizationMemberships = organizationId => getAllPages('/organizations/memberships/', { organization: organizationId });
export const createOrganization = payload => api.post('/organizations/organizations/', payload);
export const createMembership = payload => api.post('/organizations/memberships/', payload);
export const searchOrganizationUsers = (organizationId, search) => api.get(
  `/organizations/organizations/${organizationId}/user-search/`, { params: { search } }
).then(({ data }) => data);
export const updateMembership = (id, organizationId, payload) => api.patch(
  `/organizations/memberships/${id}/`, payload, { params: { organization: organizationId } }
);
export const setOrganizationVerification = (id, action) => api.post(`/organizations/organizations/${id}/${action}/`, {});
