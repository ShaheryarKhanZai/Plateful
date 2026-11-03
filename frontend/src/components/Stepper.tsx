export function Stepper({ qty, onChange, name }: { qty: number; onChange: (q: number) => void; name: string }) {
  return (
    <div className="stepper" role="group" aria-label={`Quantity of ${name}`}>
      <button type="button" aria-label={`Remove one ${name}`} onClick={() => onChange(qty - 1)}>−</button>
      <span aria-live="polite">{qty}</span>
      <button type="button" aria-label={`Add one ${name}`} onClick={() => onChange(qty + 1)} disabled={qty >= 20}>+</button>
    </div>
  );
}
