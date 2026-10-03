"use client";

import { useParams } from "next/navigation";
import { ServiceKnowledgeProfile } from "../../../../../components/service-knowledge-profile";

export default function KnowledgeProfilePage() {
  const { id } = useParams();
  return <ServiceKnowledgeProfile typeId={id} />;
}
