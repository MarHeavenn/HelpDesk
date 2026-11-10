/** Bloque de carga con la forma del contenido que sustituye (RF-92, RF-103). */
export default function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-md bg-slate-200 ${className}`}
    />
  )
}
