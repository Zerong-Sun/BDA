{{/*
Volumes for the two credential stores that need a real filesystem.

Every pod runs with readOnlyRootFilesystem and an emptyDir at /tmp, which is correct but
leaves nowhere for either of these to live:

  * BYOK provider keys are written by the API (0600, atomic replace) and read back by the
    LLM-facing workers. On an emptyDir a key saved through one API replica is invisible to
    the other and gone on restart, so this needs a shared, durable claim.
  * The LSF credential is referenced as `file:` on purpose - never an env var, which is
    visible in `docker inspect` and to every child process - so the referenced path has to
    exist inside the pod.

Without these the chart renders a deployment that passes config validation and then fails
at the first BYOK save or the first dispatch to the cluster.
*/}}

{{- define "bda.byokVolume" -}}
{{- if .Values.byokStorage.enabled -}}
- name: byok-secrets
  persistentVolumeClaim:
    claimName: {{ .Values.byokStorage.existingClaim | default (printf "%s-byok" .Release.Name) }}
{{- end }}
{{- end -}}

{{- define "bda.backendImage" -}}
{{- if .Values.image.digest -}}
{{- printf "%s@%s" .Values.image.repository .Values.image.digest -}}
{{- else -}}
{{- printf "%s:%s" .Values.image.repository .Values.image.tag -}}
{{- end -}}
{{- end -}}

{{- define "bda.frontendImage" -}}
{{- if .Values.frontendImage.digest -}}
{{- printf "%s@%s" .Values.frontendImage.repository .Values.frontendImage.digest -}}
{{- else -}}
{{- printf "%s:%s" .Values.frontendImage.repository .Values.frontendImage.tag -}}
{{- end -}}
{{- end -}}

{{- define "bda.byokVolumeMount" -}}
{{- if .Values.byokStorage.enabled -}}
- name: byok-secrets
  mountPath: {{ .Values.config.llmSecretDir | quote }}
{{- end }}
{{- end -}}

{{- define "bda.lsfVolume" -}}
{{- if .Values.lsfCredentials.secretName -}}
- name: lsf-credentials
  secret:
    secretName: {{ .Values.lsfCredentials.secretName }}
    defaultMode: 0400
{{- end }}
{{- end -}}

{{- define "bda.lsfVolumeMount" -}}
{{- if .Values.lsfCredentials.secretName -}}
- name: lsf-credentials
  mountPath: {{ .Values.lsfCredentials.mountPath | quote }}
  readOnly: true
{{- end }}
{{- end -}}

{{/*
Fail rendering rather than shipping a release that cannot dispatch.

`computeBackend: lsf` with no credential reference passes the container's own startup
validation only because that validation checks the env var, not whether the file it names
is actually mounted.
*/}}
{{- define "bda.validateLsf" -}}
{{- if eq .Values.config.computeBackend "lsf" }}
{{- if not .Values.config.lsf.sshHost }}
{{- fail "config.computeBackend is lsf but config.lsf.sshHost is empty" }}
{{- end }}
{{- if not .Values.config.lsf.remoteRoot }}
{{- fail "config.computeBackend is lsf but config.lsf.remoteRoot is empty" }}
{{- end }}
{{- if and (not .Values.lsfCredentials.keyFile) (not .Values.lsfCredentials.passwordFile) }}
{{- fail "config.computeBackend is lsf but neither lsfCredentials.keyFile nor lsfCredentials.passwordFile is set" }}
{{- end }}
{{- if not .Values.lsfCredentials.secretName }}
{{- fail "config.computeBackend is lsf but lsfCredentials.secretName is empty, so the file: reference cannot resolve" }}
{{- end }}
{{- end }}
{{- end -}}

{{- define "bda.epoOpsVolume" -}}
{{- if .Values.epoOpsCredentials.secretName -}}
- name: epo-ops-credentials
  secret:
    secretName: {{ .Values.epoOpsCredentials.secretName | quote }}
    defaultMode: 0440
    items:
      - key: {{ .Values.epoOpsCredentials.keyFile | quote }}
        path: {{ .Values.epoOpsCredentials.keyFile | quote }}
{{- end }}
{{- end -}}

{{- define "bda.epoOpsVolumeMount" -}}
{{- if .Values.epoOpsCredentials.secretName -}}
- name: epo-ops-credentials
  mountPath: {{ .Values.epoOpsCredentials.mountPath | quote }}
  readOnly: true
{{- end }}
{{- end -}}

{{- define "bda.validateEpoOps" -}}
{{- if .Values.epoOpsCredentials.secretName }}
{{- if or (not (regexMatch "^[A-Za-z0-9_][A-Za-z0-9_.-]*$" .Values.epoOpsCredentials.keyFile)) (contains ".." .Values.epoOpsCredentials.keyFile) }}
{{- fail "epoOpsCredentials.keyFile must be a simple Secret key filename" }}
{{- end }}
{{- if or (not (hasPrefix "/" .Values.epoOpsCredentials.mountPath)) (contains ".." .Values.epoOpsCredentials.mountPath) (eq "/" .Values.epoOpsCredentials.mountPath) }}
{{- fail "epoOpsCredentials.mountPath must be an absolute directory without parent traversal" }}
{{- end }}
{{- end }}
{{- end -}}
