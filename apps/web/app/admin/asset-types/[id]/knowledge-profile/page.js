"use client";

import { useParams } from "next/navigation";
import { AssetKnowledgeProfile } from "../../../../../components/asset-knowledge-profile";

export default function KnowledgeProfilePage() {
  const { id } = useParams();
  return <AssetKnowledgeProfile typeId={id} />;
}
