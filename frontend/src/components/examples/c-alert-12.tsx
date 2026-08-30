import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/reui/alert"
import { Frame, FramePanel } from "@/components/reui/frame"
import { InfoIcon } from "@phosphor-icons/react"

export function Pattern() {
  return (
    <div className="mx-auto mb-auto w-full max-w-lg">
      <Frame>
        <FramePanel className="overflow-hidden p-0!">
          <Alert className="border-0 shadow-none">
            <InfoIcon className="text-destructive" />
            <AlertTitle>System Update</AlertTitle>
            <AlertDescription>
              A new system update is available. Please restart your application
              to apply the changes.
            </AlertDescription>
          </Alert>
        </FramePanel>
      </Frame>
    </div>
  )
}