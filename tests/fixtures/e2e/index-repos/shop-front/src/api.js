export async function createOrder(data) {
  return fetch('/api/orders', { method: 'POST', body: JSON.stringify(data) });
}

export async function getOrder(id) {
  return fetch(`/api/orders/${id}`);
}
