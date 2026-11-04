import { useState } from 'react'
import { api, type CatalogModel } from '../api'
import { CodeBlock } from '../components/CopyButton'
import { useAsync } from '../useAsync'

const KEY_PLACEHOLDER = 'sk-ath-ISI-KEY-ANDA'

interface Config {
  api_base_url: string
}

export function QuickstartPage() {
  // Keep plaintext keys only on the creation screen, never in browser history state.
  const [enteredKey, setEnteredKey] = useState('')
  const key = /^sk-ath-[A-Za-z0-9]{40}$/.test(enteredKey.trim())
    ? enteredKey.trim()
    : KEY_PLACEHOLDER
  const config = useAsync('config', () => api<Config>('/config'))
  const models = useAsync('models', () => api<CatalogModel[]>('/models'))

  const base = config.data?.api_base_url ?? 'https://atheena.online/v1'
  const root = base.replace(/\/v1$/, '')
  const openaiModels = models.data?.filter((m) => m.api_format !== 'anthropic') ?? []
  const anthropicModels = models.data?.filter((m) => m.api_format !== 'openai') ?? []
  const claudeModel =
    anthropicModels.find((m) => m.name.startsWith('claude'))?.name ??
    anthropicModels[0]?.name ??
    'nama-model'
  const firstModel = openaiModels[0]?.name ?? 'nama-model'

  const opencode = JSON.stringify(
    {
      $schema: 'https://opencode.ai/config.json',
      provider: {
        atheena: {
          npm: '@ai-sdk/openai-compatible',
          name: 'Atheena',
          options: { baseURL: base, apiKey: key },
          models: Object.fromEntries(openaiModels.map((m) => [m.name, { name: m.name }])),
        },
      },
    },
    null,
    2,
  )

  return (
    <div className="page">
      <header className="page__head">
        <h1>Mulai memakai Atheena</h1>
        <p className="muted">
          Semua tool memakai satu alamat dan satu key yang sama. Tidak perlu tahu provider asli
          model.
        </p>
      </header>

      <label className="field">
        <span className="field__label">Paste API key kamu</span>
        <input
          type="password"
          className="input"
          value={enteredKey}
          onChange={(e) => setEnteredKey(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          placeholder="sk-ath-…"
        />
      </label>
      <p className="muted">
        Key hanya dipakai di halaman ini untuk mengisi contoh konfigurasi. Tidak disimpan di
        browser. Salin konfigurasi lalu jalankan OpenCode.
      </p>
      {enteredKey && key === KEY_PLACEHOLDER && <p role="alert">Format API key belum lengkap.</p>}

      <section className="section guide" aria-labelledby="opencode">
        <h2 id="opencode">OpenCode</h2>
        <p className="muted">
          Simpan sebagai <code>~/.config/opencode/opencode.json</code> (atau{' '}
          <code>opencode.json</code> di folder proyek). Model tampil sebagai{' '}
          <code>atheena/nama-model</code>.
        </p>
        <CodeBlock label="opencode.json" code={opencode} />
        <CodeBlock label="Jalankan" code="opencode" />
      </section>

      <section className="section guide" aria-labelledby="claude-code">
        <h2 id="claude-code">Claude Code</h2>
        <p className="muted">
          Claude Code memakai format Anthropic; portal melayaninya di alamat yang sama. Hanya model
          yang mendukung format Anthropic yang bisa dipakai di sini.
        </p>
        <CodeBlock
          label="Terminal"
          code={[
            `export ANTHROPIC_BASE_URL="${root}"`,
            `export ANTHROPIC_AUTH_TOKEN="${key}"`,
            `export ANTHROPIC_MODEL="${claudeModel}"`,
            'claude',
          ].join('\n')}
        />
      </section>

      <section className="section guide" aria-labelledby="cursor">
        <h2 id="cursor">Cursor</h2>
        <ol className="plain-steps">
          <li>Buka Settings, lalu Models.</li>
          <li>
            Isi <strong>OpenAI API Key</strong> dengan key Anda, aktifkan{' '}
            <strong>Override OpenAI Base URL</strong>, lalu isi <code>{base}</code>.
          </li>
          <li>
            Tambahkan nama model, misalnya <code>{firstModel}</code>.
          </li>
        </ol>
      </section>

      <section className="section guide" aria-labelledby="curl">
        <h2 id="curl">curl</h2>
        <CodeBlock
          label="Terminal"
          code={[
            `curl ${base}/chat/completions \\`,
            `  -H "Authorization: Bearer ${key}" \\`,
            '  -H "Content-Type: application/json" \\',
            `  -d '{"model": "${firstModel}", "messages": [{"role": "user", "content": "Halo"}]}'`,
          ].join('\n')}
        />
      </section>

      {models.data && (
        <section className="section" aria-labelledby="model">
          <h2 id="model">Model yang bisa Anda pakai</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Nama</th>
                  <th scope="col">Format</th>
                  <th scope="col">Kategori</th>
                </tr>
              </thead>
              <tbody>
                {models.data.map((m) => (
                  <tr key={m.name}>
                    <td className="num">{m.name}</td>
                    <td className="muted">
                      {m.api_format === 'both'
                        ? 'OpenAI dan Anthropic'
                        : m.api_format === 'openai'
                          ? 'OpenAI'
                          : 'Anthropic'}
                    </td>
                    <td className="muted">{m.category === 'official' ? 'Resmi' : 'Eksperimen'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted field__label">
            Model eksperimen ditolak untuk proyek yang hanya boleh memakai provider resmi (header
            <code> X-Project</code>).
          </p>
        </section>
      )}
    </div>
  )
}
