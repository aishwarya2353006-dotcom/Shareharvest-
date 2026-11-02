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

export const getMyCompliance = () => getAllPages('/compliance/organization-compliance/my-compliance/');
export const getOrganizationCompliance = organizationId => getAllPages(
  '/compliance/organization-compliance/',
  organizationId == null ? {} : { organization: organizationId },
);
export const submitCompliance = (payload) => api.post('/compliance/organization-compliance/', payload);
export const verifyCompliance = (id, payload = {}) => api.post(
  `/compliance/organization-compliance/${id}/verify/`, { ...payload, action: 'verify' }
);
export const rejectCompliance = (id, payload = {}) => api.post(
  `/compliance/organization-compliance/${id}/reject/`, { ...payload, action: 'reject' }
);

export const getMyAllergenDeclarations = () => getAllPages('/compliance/allergen-declarations/my-declarations/');
export const getAllergenDeclarations = () => getAllPages('/compliance/allergen-declarations/');
export const submitAllergenDeclaration = (payload) => api.post('/compliance/allergen-declarations/', payload);
export const reviewAllergenDeclaration = (id, payload) => api.post(`/compliance/allergen-declarations/${id}/${payload.action === 'verify' ? 'verify' : 'reject'}/`, payload);

export const getComplianceDocuments = () => getAllPages('/compliance/compliance-documents/');
export const submitComplianceDocument = (payload) => api.post('/compliance/compliance-documents/', payload);

export const ALLERGEN_CHOICES = [
  { value: 'cereals_containing_gluten', label: 'Cereals containing gluten' },
  { value: 'crustaceans', label: 'Crustaceans' },
  { value: 'eggs', label: 'Eggs' },
  { value: 'fish', label: 'Fish' },
  { value: 'peanuts', label: 'Peanuts' },
  { value: 'soybeans', label: 'Soybeans' },
  { value: 'milk', label: 'Milk' },
  { value: 'tree_nuts', label: 'Tree nuts' },
  { value: 'sulphites', label: 'Sulphites' },
  { value: 'lupin', label: 'Lupin' },
  { value: 'molluscs', label: 'Molluscs' },
  { value: 'sesame_seeds', label: 'Sesame seeds' },
];

export const getAllergenLabel = value => {
  const found = ALLERGEN_CHOICES.find(choice => choice.value === value);
  return found ? found.label : value;
};

export const COMPLIANCE_STATUS_LABELS = {
  pending: 'Pending submission',
  submitted: 'Submitted for review',
  verified: 'Verified',
  rejected: 'Rejected',
  expired: 'Expired',
};
