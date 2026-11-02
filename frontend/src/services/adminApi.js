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

export async function getAdminDashboardData() {
  const [organizations, donations, pendingRequests, complianceRecords, allergenDeclarations] = await Promise.all([
    getAllPages('/organizations/organizations/'),
    getAllPages('/donations/donations/'),
    getAllPages('/donation-requests/', { status: 'pending' }),
    getAllPages('/compliance/organization-compliance/'),
    getAllPages('/compliance/allergen-declarations/'),
  ]);

  return { organizations, donations, pendingRequests, complianceRecords, allergenDeclarations };
}
