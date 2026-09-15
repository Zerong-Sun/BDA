/** A consistent, code-native identity system. Motion responds to interaction;
 * idle avatars never imply that a task is running. */
export function BotAvatar({ id, stance = 'produce' }: { id: string; stance?: string }) {
  const variation = Array.from(id).reduce((sum, char) => sum + char.charCodeAt(0), 0) % 3
  return <span className={`bot-avatar bot-avatar--${stance} bot-avatar--${variation}`} aria-hidden="true">
    <span className="bot-antenna" /><span className="bot-face"><i /><i /></span>
  </span>
}
