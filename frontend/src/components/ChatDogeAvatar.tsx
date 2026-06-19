import chatDoge from "../assets/chat-doge.png";

export function ChatDogeAvatar() {
  return (
    <div className="assistant-avatar" role="img" aria-label="챗도지">
      <img src={chatDoge} alt="" />
    </div>
  );
}
