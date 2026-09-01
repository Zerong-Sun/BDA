import { useId, useState, type ReactNode } from 'react'
import type { Project } from '../../lib/api/projects'
import { useI18n } from '../../lib/i18n'

type StructureKind =
  | 'molecule'
  | 'toxin'
  | 'complex'
  | 'membrane'
  | 'enzyme'
  | 'collagen'
  | 'scaffold'
  | 'barrel'
  | 'membrane-enzyme'
  | 'nanocage'
  | 'antifungal'
  | 'protein'

interface RepresentativeStructure {
  kind: StructureKind
  name: { zh: string; en: string }
  detail: { zh: string; en: string }
  pdbId?: string
}

const REPRESENTATIVE_STRUCTURES: Record<string, RepresentativeStructure> = {
  PD1: {
    kind: 'complex',
    name: { zh: 'PD-1 · 特瑞普利单抗', en: 'PD-1 · toripalimab' },
    detail: { zh: '抗体 Fab 结合界面 · PDB 6JBT', en: 'Antibody Fab interface · PDB 6JBT' },
    pdbId: '6JBT',
  },
  sweet_protein_design: {
    kind: 'protein',
    name: { zh: '甜味蛋白设计', en: 'Sweet-protein design' },
    detail: { zh: '项目结构由目标与制品决定', en: 'Project structure comes from its target and artifacts' },
  },
  binder_design: {
    kind: 'complex',
    name: { zh: '结合蛋白 · 靶点', en: 'Binder · target' },
    detail: { zh: '代表性蛋白结合界面', en: 'Representative protein interface' },
  },
  enzyme_design: {
    kind: 'enzyme',
    name: { zh: '酶 · 底物', en: 'Enzyme · substrate' },
    detail: { zh: '代表性催化口袋', en: 'Representative catalytic pocket' },
  },
  biomaterial_design: {
    kind: 'collagen',
    name: { zh: '胶原三螺旋', en: 'Collagen triple helix' },
    detail: { zh: '代表性生物材料支架', en: 'Representative biomaterial scaffold' },
  },
  scaffold_redesign: {
    kind: 'scaffold',
    name: { zh: 'α/β 蛋白支架', en: 'α/β protein scaffold' },
    detail: { zh: '代表性重设计折叠', en: 'Representative redesign fold' },
  },
  protein_design: {
    kind: 'protein',
    name: { zh: '从头设计螺旋束', en: 'De novo helical bundle' },
    detail: { zh: '代表性设计蛋白', en: 'Representative designed protein' },
  },
}

function representativeForProject(project: Project): RepresentativeStructure {
  const sourceKey = project.source_project_key?.toUpperCase()
  if (sourceKey === 'PD1') return REPRESENTATIVE_STRUCTURES.PD1

  const searchable = `${project.name} ${project.summary ?? ''}`.toLowerCase()
  if (/pd[-_ ]?1|pd[-_ ]?l1|checkpoint|检查点/.test(searchable)) return REPRESENTATIVE_STRUCTURES.PD1
  if (REPRESENTATIVE_STRUCTURES[project.project_type]) return REPRESENTATIVE_STRUCTURES[project.project_type]
  if (/enzyme|cataly|酶|催化/.test(searchable)) return REPRESENTATIVE_STRUCTURES.enzyme_design
  if (/binder|antibody|complex|结合|抗体|复合物/.test(searchable)) return REPRESENTATIVE_STRUCTURES.binder_design
  if (/material|collagen|silk|材料|胶原|丝/.test(searchable)) return REPRESENTATIVE_STRUCTURES.biomaterial_design
  return REPRESENTATIVE_STRUCTURES.protein_design
}

function Helix({ x, color, delay = 0 }: { x: number; color: string; delay?: number }) {
  return (
    <g transform={`translate(${x} 13)`} opacity={0.92}>
      <path
        d="M0 0 C18 7 -18 15 0 23 C18 31 -18 39 0 47 C18 55 -18 63 0 71 C18 79 -18 87 0 95"
        fill="none"
        stroke={color}
        strokeWidth="6"
        strokeLinecap="round"
        style={{ animationDelay: `${delay}ms` }}
      />
      <path
        d="M0 0 C-18 7 18 15 0 23 C-18 31 18 39 0 47 C-18 55 18 63 0 71 C-18 79 18 87 0 95"
        fill="none"
        stroke="var(--bg-surface-3)"
        strokeWidth="2"
        strokeLinecap="round"
        opacity="0.62"
      />
    </g>
  )
}

function StructureGraphic({ kind, gradientId }: { kind: StructureKind; gradientId: string }) {
  const warm = 'var(--accent)'
  const cool = 'var(--info)'
  const green = 'var(--success)'
  const surface = 'var(--bg-surface-3)'

  const graphics: Record<StructureKind, ReactNode> = {
    molecule: (
      <g transform="translate(18 18) rotate(-8 62 45)">
        <g fill="none" stroke={warm} strokeWidth="3.5" strokeLinejoin="round">
          <path d="M18 52 36 37 58 44 62 66 44 80 22 72Z" />
          <path d="M58 44 77 30 98 39 100 61 82 74 62 66" />
          <path d="M77 30 75 10M98 39l18-10M100 61l18 9M44 80l3 19" />
          <path d="M27 54 39 44M82 38l11 6M82 67l11-8" opacity="0.55" />
        </g>
        <g fill={surface} stroke={warm} strokeWidth="3">
          <circle cx="18" cy="52" r="6" /><circle cx="36" cy="37" r="5" />
          <circle cx="58" cy="44" r="6" /><circle cx="62" cy="66" r="5" />
          <circle cx="44" cy="80" r="6" /><circle cx="22" cy="72" r="5" />
          <circle cx="77" cy="30" r="6" /><circle cx="98" cy="39" r="5" />
          <circle cx="100" cy="61" r="6" /><circle cx="82" cy="74" r="5" />
        </g>
        <circle cx="75" cy="10" r="7" fill={green} />
        <circle cx="118" cy="29" r="5" fill={cool} />
        <circle cx="118" cy="70" r="5" fill={warm} />
      </g>
    ),
    toxin: (
      <g transform="translate(14 8)">
        <path d="M16 77C8 52 19 24 46 18c21-5 35 4 39 18 6 19-11 29-22 39-12 11-8 26-23 31-12 4-20-10-24-29Z" fill={`url(#${gradientId})`} opacity="0.82" />
        <path d="M73 31c10-17 36-16 51-2 14 13 11 34-3 42-16 10-31 3-45-4-16-8-13-20-3-36Z" fill={cool} opacity="0.65" />
        <path d="M62 74c10-14 29-12 47-3 18 9 23 29 10 39-16 13-35 1-52-7-15-7-16-16-5-29Z" fill={green} opacity="0.65" />
        <g fill="none" stroke={surface} strokeWidth="2.2" opacity="0.78">
          <path d="M26 84c27-17 13-54 43-58M23 65c27-14 22-31 51-34M81 38c14 7 24 16 35 25M76 49c15 2 29 7 42 16M69 86c18-5 33 3 47 16M72 96c16-4 27 2 37 11" />
        </g>
      </g>
    ),
    complex: (
      <g transform="translate(10 8)">
        <path d="M19 32C31 10 60 7 78 22c14 12 12 27 1 38-9 9-8 24-23 30-20 9-47-4-47-27 0-11 4-21 10-31Z" fill={`url(#${gradientId})`} opacity="0.86" />
        <path d="M136 34c-12-22-41-27-58-11-10 10-6 26 2 37 7 10 4 24 18 31 21 11 50-1 51-25 1-12-5-23-13-32Z" fill={cool} opacity="0.76" />
        <g fill="none" stroke={surface} strokeWidth="2.4" opacity="0.72">
          <path d="M22 47c17-19 34-21 52-11M18 61c20-17 36-16 59-4M31 78c16-12 27-7 38 0M137 48c-17-17-34-20-51-10M141 64c-19-15-37-14-58-4M127 80c-14-10-27-8-38-1" />
        </g>
        <g fill={warm}>
          <circle cx="76" cy="46" r="4" /><circle cx="80" cy="57" r="3.5" /><circle cx="78" cy="68" r="3" />
        </g>
      </g>
    ),
    membrane: (
      <g transform="translate(15 2)">
        <g opacity="0.42" stroke={cool} strokeWidth="2">
          <path d="M0 23h130M0 102h130" />
          {Array.from({ length: 9 }).map((_, index) => <circle key={index} cx={index * 16 + 1} cy="23" r="4" fill={cool} />)}
          {Array.from({ length: 9 }).map((_, index) => <circle key={index} cx={index * 16 + 1} cy="102" r="4" fill={cool} />)}
        </g>
        <Helix x={21} color={warm} /><Helix x={37} color={cool} delay={35} />
        <Helix x={53} color={warm} delay={70} /><Helix x={69} color={green} delay={105} />
        <Helix x={85} color={warm} delay={140} /><Helix x={101} color={cool} delay={175} />
        <Helix x={117} color={warm} delay={210} />
      </g>
    ),
    enzyme: (
      <g transform="translate(12 7)">
        <path d="M20 29C36 4 75 4 93 20c12 10 10 22 19 31 11 11 26 16 25 34-2 25-35 38-55 26-12-7-22-6-35-3-23 5-43-12-40-34 2-16 4-29 13-45Z" fill={`url(#${gradientId})`} opacity="0.84" />
        <path d="M51 15c22 12 28 24 23 40-5 17 6 28 27 36" fill="none" stroke={surface} strokeWidth="3" opacity="0.72" />
        <path d="M24 46c22-14 38-9 48 4M24 93c17-18 36-15 51-2M96 25c-17 12-20 25-13 42M107 105c13-14 17-28 9-42" fill="none" stroke={surface} strokeWidth="2.3" opacity="0.62" />
        <g stroke={cool} strokeWidth="3" fill={surface}>
          <path d="m65 67 13-10 15 7 1 17-14 9-15-7Z" />
          <circle cx="65" cy="67" r="4" /><circle cx="78" cy="57" r="4" /><circle cx="93" cy="64" r="4" /><circle cx="94" cy="81" r="4" /><circle cx="80" cy="90" r="4" /><circle cx="65" cy="83" r="4" />
        </g>
      </g>
    ),
    collagen: (
      <g transform="translate(18 10) rotate(-7 60 52)" fill="none" strokeLinecap="round">
        <path d="M8 0c55 27 64 66 114 104M8 104C55 75 67 32 122 0" stroke={warm} strokeWidth="7" opacity="0.9" />
        <path d="M34 0c-37 34-16 70 63 104M97 0c-79 34-100 70-63 104" stroke={cool} strokeWidth="6" opacity="0.75" />
        <path d="M61 0c55 35 46 72-22 104M70 0C2 32-7 70 48 104" stroke={green} strokeWidth="5" opacity="0.7" />
        <g stroke={surface} strokeWidth="1.5" opacity="0.6"><path d="M22 18h88M16 43h99M18 68h93M28 91h75" /></g>
      </g>
    ),
    scaffold: (
      <g transform="translate(20 12)">
        <path d="M8 12h42l-9 9 9 9H8l9-9Z" fill={cool} opacity="0.82" />
        <path d="M2 42h50l-10 9 10 9H2l10-9Z" fill={green} opacity="0.7" />
        <path d="M8 72h42l-9 9 9 9H8l9-9Z" fill={cool} opacity="0.82" />
        <g transform="translate(87 0)"><Helix x={0} color={warm} /></g>
        <path d="M49 21c26-5 14 31 37 30M49 81c23 5 13-31 36-30" fill="none" stroke={warm} strokeWidth="3" strokeLinecap="round" opacity="0.75" />
      </g>
    ),
    barrel: (
      <g transform="translate(29 8)">
        <ellipse cx="51" cy="17" rx="39" ry="13" fill={cool} opacity="0.35" />
        <g fill="none" strokeLinecap="round" strokeWidth="7">
          <path d="M15 17c-7 28-3 61 13 90" stroke={warm} />
          <path d="M30 12c-5 32 0 67 13 99" stroke={cool} />
          <path d="M48 10c-2 31 1 70 3 102" stroke={green} />
          <path d="M67 12c6 29 5 66-1 98" stroke={warm} />
          <path d="M84 18c10 27 5 61-5 88" stroke={cool} />
        </g>
        <ellipse cx="52" cy="106" rx="29" ry="9" fill="none" stroke={green} strokeWidth="3" opacity="0.65" />
        <g transform="translate(36 48) rotate(-12 17 13)" fill={surface} stroke={warm} strokeWidth="2.5">
          <path d="m3 13 13-9 15 7 2 16-13 10-16-7Z" />
          <circle cx="3" cy="13" r="3.5" /><circle cx="16" cy="4" r="3.5" /><circle cx="31" cy="11" r="3.5" /><circle cx="33" cy="27" r="3.5" /><circle cx="20" cy="37" r="3.5" /><circle cx="4" cy="30" r="3.5" />
        </g>
      </g>
    ),
    'membrane-enzyme': (
      <g transform="translate(12 4)">
        <g opacity="0.35" stroke={cool} strokeWidth="2"><path d="M0 27h136M0 99h136" /></g>
        {[18, 34, 50, 86, 102, 118].map((x, index) => <Helix key={x} x={x} color={index % 2 ? cool : warm} delay={index * 35} />)}
        <path d="M47 57c8-20 39-24 56-8 14 13 8 31-3 42-14 14-44 12-55-5-6-9-3-19 2-29Z" fill={`url(#${gradientId})`} opacity="0.92" />
        <path d="M56 61c10-9 27-8 38 1M54 78c14 8 28 7 40-3" fill="none" stroke={surface} strokeWidth="2.4" opacity="0.7" />
        <circle cx="76" cy="68" r="7" fill={surface} stroke={green} strokeWidth="3" />
      </g>
    ),
    nanocage: (
      <g transform="translate(26 8)" fill="none" strokeLinejoin="round">
        <path d="m54 0 45 25 10 50-35 40H34L0 75l10-50Z" stroke={warm} strokeWidth="4" opacity="0.85" />
        <path d="M10 25 54 48 99 25M0 75l54-27 55 27M34 115l20-67 20 67M54 0v48" stroke={cool} strokeWidth="3" opacity="0.72" />
        <path d="m10 25 24 90M99 25 74 115M0 75h109" stroke={green} strokeWidth="2.5" opacity="0.55" />
        <g fill={surface} stroke={warm} strokeWidth="3">
          {[[54,0],[10,25],[99,25],[0,75],[109,75],[34,115],[74,115],[54,48]].map(([cx,cy]) => <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="6" />)}
        </g>
        <circle cx="54" cy="61" r="17" fill={warm} opacity="0.16" stroke={warm} strokeWidth="2" />
      </g>
    ),
    antifungal: (
      <g transform="translate(26 10)">
        <path d="M11 30C21 8 50 1 70 14c15 10 13 25 26 35 16 12 14 36-1 49-17 14-39 3-57 7-21 5-39-12-36-33 2-15 2-29 9-42Z" fill={`url(#${gradientId})`} opacity="0.82" />
        <path d="M18 40c17-18 35-16 49-4M11 69c20-17 39-14 55-1M22 94c16-15 32-11 45-3" fill="none" stroke={surface} strokeWidth="2.6" opacity="0.7" />
        <path d="M71 19c-17 24-8 42 18 55M46 28c27 16 31 42 13 69" fill="none" stroke={cool} strokeWidth="4" strokeLinecap="round" />
        <g fill={warm}><circle cx="40" cy="31" r="4" /><circle cx="82" cy="48" r="4" /><circle cx="31" cy="79" r="4" /><circle cx="74" cy="91" r="4" /></g>
        <g stroke={warm} strokeWidth="2.5"><path d="m40 31 42 17M31 79l43 12" /></g>
      </g>
    ),
    protein: (
      <g transform="translate(27 5)">
        <Helix x={20} color={warm} /><Helix x={47} color={cool} delay={50} />
        <Helix x={74} color={green} delay={100} /><Helix x={101} color={warm} delay={150} />
        <path d="M20 108c22 12 33-9 54 0 18 8 28-8 47-1" fill="none" stroke={cool} strokeWidth="3" strokeLinecap="round" opacity="0.7" />
      </g>
    ),
  }

  return (
    <svg viewBox="0 0 160 125" className="h-full w-full" aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={warm} />
          <stop offset="1" stopColor={green} />
        </linearGradient>
        <radialGradient id={`${gradientId}-glow`} cx="50%" cy="45%" r="62%">
          <stop offset="0" stopColor={warm} stopOpacity="0.16" />
          <stop offset="1" stopColor={warm} stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="160" height="125" fill={`url(#${gradientId}-glow)`} />
      <g opacity="0.12" fill="var(--text-muted)">
        {Array.from({ length: 28 }).map((_, index) => (
          <circle key={index} cx={(index * 43) % 158 + 1} cy={(index * 29) % 121 + 2} r="1" />
        ))}
      </g>
      {graphics[kind]}
    </svg>
  )
}

export function RepresentativeStructurePreview({ project }: { project: Project }) {
  const { language } = useI18n()
  const structure = representativeForProject(project)
  const gradientId = useId().replace(/:/g, '')
  const imageUrl = structure.pdbId
    ? `https://cdn.rcsb.org/images/structures/${structure.pdbId.toLowerCase()}_assembly-1.jpeg`
    : null
  const [failedImageUrl, setFailedImageUrl] = useState<string | null>(null)
  const imageFailed = imageUrl === failedImageUrl
  const locale = language === 'zh' ? 'zh' : 'en'
  const eyebrow = locale === 'zh' ? '相关结构' : 'Related structure'
  const ariaLabel = `${eyebrow}: ${structure.name[locale]}, ${structure.detail[locale]}`

  return (
    <div
      className="relative h-[180px] w-full overflow-hidden rounded border border-border-soft bg-bg-canvas"
      role="img"
      aria-label={ariaLabel}
    >
      <div className="absolute inset-0 pb-10 pt-5">
        {imageUrl && !imageFailed ? (
          <img
            src={imageUrl}
            alt=""
            loading="eager"
            decoding="async"
            className="h-full w-full object-contain"
            onError={() => setFailedImageUrl(imageUrl)}
          />
        ) : (
          <StructureGraphic kind={structure.kind} gradientId={gradientId} />
        )}
      </div>
      <div className="absolute left-3 top-2 rounded-full border border-border-soft bg-surface-1/85 px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.14em] text-text-muted backdrop-blur-sm">
        {eyebrow}
      </div>
      <div className="absolute inset-x-0 bottom-0 border-t border-border-soft bg-surface-1/90 px-3 py-2 backdrop-blur-sm">
        <p className="truncate text-xs font-semibold text-text-primary">{structure.name[locale]}</p>
        <p className="truncate text-[10px] text-text-muted">{structure.detail[locale]}</p>
      </div>
    </div>
  )
}
