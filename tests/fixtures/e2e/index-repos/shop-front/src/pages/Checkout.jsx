import { createOrder } from '../api';

export default function Checkout() {
  return <form onSubmit={(e) => { e.preventDefault(); createOrder({}); }}><button>Оформить</button></form>;
}
