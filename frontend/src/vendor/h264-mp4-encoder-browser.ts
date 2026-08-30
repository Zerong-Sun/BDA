import encoderBundleUrl from 'h264-mp4-encoder/embuild/dist/h264-mp4-encoder.web.js?url'

interface BrowserEncoderModule {
  createH264MP4Encoder: () => Promise<unknown>
}

declare global {
  interface Window {
    HME?: BrowserEncoderModule
  }
}

let encoderModulePromise: Promise<BrowserEncoderModule> | null = null

function loadEncoderModule(): Promise<BrowserEncoderModule> {
  if (window.HME) return Promise.resolve(window.HME)
  if (encoderModulePromise) return encoderModulePromise

  encoderModulePromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = encoderBundleUrl
    script.async = true
    script.onload = () => {
      if (window.HME) resolve(window.HME)
      else reject(new Error('The browser H.264 encoder did not expose its module.'))
    }
    script.onerror = () => reject(new Error('The browser H.264 encoder could not be loaded.'))
    document.head.appendChild(script)
  })

  return encoderModulePromise
}

export async function createH264MP4Encoder(): Promise<unknown> {
  const encoderModule = await loadEncoderModule()
  return encoderModule.createH264MP4Encoder()
}
