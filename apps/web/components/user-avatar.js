"use client";

import { useEffect, useState } from "react";
import { initialsForName, validAvatarUrl } from "../lib/user-presentation.mjs";

export function UserAvatar({ displayName, imageUrl = null, size = 34 }) {
  const safeImageUrl = validAvatarUrl(imageUrl);
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => { setImageFailed(false); }, [safeImageUrl]);

  const style = { height: `${size}px`, width: `${size}px` };
  if (safeImageUrl && !imageFailed) {
    return <span className="user-avatar" style={style}><img alt="" onError={() => setImageFailed(true)} src={safeImageUrl} /></span>;
  }
  return <span aria-hidden="true" className="user-avatar user-avatar-initials" style={style}>{initialsForName(displayName)}</span>;
}
