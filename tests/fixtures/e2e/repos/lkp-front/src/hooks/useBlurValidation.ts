export async function validatePromocodeOnBlur(value: string): Promise<'exists' | 'not_found' | 'error'> {
  try {
    const res = await fetch('/api/questionnaire/promocode/check', {
      method: 'POST',
      body: JSON.stringify({ promo_code: value }),
    });
    const data = await res.json();
    return data.status;
  } catch {
    return 'error';
  }
}
