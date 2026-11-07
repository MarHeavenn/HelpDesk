import { useEffect, useId, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '@/api/httpClient'
import { useAuth } from '@/context/AuthContext'
import { firstAllowedRoute } from '@/lib/permissions'
import { strings } from '@/lib/strings'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

interface FieldErrors {
  email?: string
  password?: string
}

function validate(email: string, password: string): FieldErrors {
  const errors: FieldErrors = {}

  if (!email.trim()) errors.email = strings.auth.requiredEmail
  else if (!EMAIL_PATTERN.test(email.trim())) {
    errors.email = strings.auth.invalidEmail
  }

  if (!password) errors.password = strings.auth.requiredPassword

  return errors
}

/** Pantalla de acceso real contra HU-01 (RF-77). */
export default function LoginPage() {
  const { user, status, login } = useAuth()
  const navigate = useNavigate()
  const emailId = useId()
  const passwordId = useId()
  const emailErrorId = useId()
  const passwordErrorId = useId()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (status === 'authenticated' && user) {
      navigate(firstAllowedRoute(user.role), { replace: true })
    }
  }, [status, user, navigate])

  if (status === 'loading') {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <p role="status" className="text-sm text-slate-600">
          {strings.auth.checkingSession}
        </p>
      </main>
    )
  }

  if (status === 'authenticated') return null

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)

    const errors = validate(email, password)
    setFieldErrors(errors)
    if (errors.email || errors.password) return

    setSubmitting(true)
    try {
      const authenticated = await login(email.trim(), password)
      navigate(firstAllowedRoute(authenticated.role), { replace: true })
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        setFormError(strings.auth.invalidCredentials)
      } else if (cause instanceof ApiError) {
        setFormError(cause.detail)
      } else {
        setFormError(strings.auth.networkError)
      }
      setSubmitting(false)
    }
  }

  function clearFieldError(field: keyof FieldErrors) {
    setFieldErrors((current) => {
      if (!current[field]) return current
      return { ...current, [field]: undefined }
    })
    setFormError(null)
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-primary">
            {strings.app.name}
          </p>
          <h1 className="mt-3 text-2xl font-semibold text-slate-900">
            {strings.auth.title}
          </h1>
          <p className="mt-1 text-sm text-slate-600">{strings.auth.subtitle}</p>
        </div>

        <form
          noValidate
          onSubmit={handleSubmit}
          className="space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
        >
          {formError ? (
            <p
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
            >
              {formError}
            </p>
          ) : null}

          <div>
            <label
              htmlFor={emailId}
              className="block text-sm font-medium text-slate-700"
            >
              {strings.auth.email}
            </label>
            <input
              id={emailId}
              name="email"
              type="email"
              autoComplete="email"
              disabled={submitting}
              required
              aria-invalid={Boolean(fieldErrors.email)}
              aria-describedby={
                fieldErrors.email ? emailErrorId : undefined
              }
              value={email}
              onChange={(event) => {
                setEmail(event.target.value)
                clearFieldError('email')
              }}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30 disabled:bg-slate-100 aria-[invalid=true]:border-red-500"
            />
            {fieldErrors.email ? (
              <p id={emailErrorId} role="alert" className="mt-1 text-sm text-red-600">
                {fieldErrors.email}
              </p>
            ) : null}
          </div>

          <div>
            <label
              htmlFor={passwordId}
              className="block text-sm font-medium text-slate-700"
            >
              {strings.auth.password}
            </label>
            <input
              id={passwordId}
              name="password"
              type="password"
              autoComplete="current-password"
              disabled={submitting}
              required
              aria-invalid={Boolean(fieldErrors.password)}
              aria-describedby={
                fieldErrors.password ? passwordErrorId : undefined
              }
              value={password}
              onChange={(event) => {
                setPassword(event.target.value)
                clearFieldError('password')
              }}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/30 disabled:bg-slate-100 aria-[invalid=true]:border-red-500"
            />
            {fieldErrors.password ? (
              <p
                id={passwordErrorId}
                role="alert"
                className="mt-1 text-sm text-red-600"
              >
                {fieldErrors.password}
              </p>
            ) : null}
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-hover focus:outline-none focus:ring-2 focus:ring-primary/40 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {submitting ? strings.auth.submitting : strings.auth.submit}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-500">
          {strings.app.name} {strings.app.version} · {strings.app.prototype}
        </p>
      </div>
    </main>
  )
}
