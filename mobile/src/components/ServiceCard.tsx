import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, Text, View } from "react-native";
import { formatPrice, type ServiceRecord } from "../../public/service-client.mjs";
import { colors, serif } from "../theme";

type Props = {
  service: Pick<ServiceRecord, "name" | "description" | "base_price_minor" | "estimated_duration_minutes" | "unit_label" | "is_active">;
  preview?: boolean;
};

export function ServiceCard({ service, preview = false }: Props) {
  return (
    <View style={styles.card}>
      <View style={styles.row}>
        <View style={styles.car}><Ionicons name="car-outline" size={23} color={colors.forest} /></View>
        <View style={[styles.badge, !service.is_active && styles.inactive]}>
          <View style={[styles.dot, !service.is_active && { backgroundColor: colors.muted }]} />
          <Text style={styles.badgeText}>{service.is_active ? (preview ? "Available for quotes" : "Active") : "Inactive"}</Text>
        </View>
      </View>
      {preview && <Text style={styles.eyebrow}>YOUR SERVICE, AT A GLANCE</Text>}
      <Text style={styles.name}>{service.name}</Text>
      {!!service.description && <Text style={styles.description}>{service.description}</Text>}
      <View style={styles.bottom}>
        <View style={{ flex: 1 }}>
          <Text style={styles.priceLabel}>{service.base_price_minor === null ? "Made to fit the job" : "Starting at · USD"}</Text>
          <Text style={styles.price}>{formatPrice(service.base_price_minor)}</Text>
        </View>
        <View style={styles.meta}>
          <Text style={styles.metaText}>{service.estimated_duration_minutes ? `${service.estimated_duration_minutes} min` : "Flexible duration"}</Text>
          <Text style={styles.metaText}>per {service.unit_label}</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderWidth: 1, borderColor: colors.line, borderRadius: 16, backgroundColor: colors.white, padding: 22 },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10 },
  car: { height: 45, width: 45, backgroundColor: colors.light, borderRadius: 13, justifyContent: "center", alignItems: "center" },
  badge: { flexDirection: "row", alignItems: "center", gap: 5, backgroundColor: colors.light, borderRadius: 30, paddingHorizontal: 10, paddingVertical: 7 },
  inactive: { backgroundColor: "#F0F1EC" },
  dot: { height: 5, width: 5, borderRadius: 3, backgroundColor: "#5B7B45" },
  badgeText: { fontSize: 10, color: "#60754E", fontWeight: "500" },
  eyebrow: { fontSize: 8, letterSpacing: 1.5, color: colors.muted, marginTop: 22 },
  name: { fontFamily: serif, fontSize: 27, lineHeight: 34, letterSpacing: -0.6, color: colors.ink, marginTop: 16 },
  description: { fontSize: 13, lineHeight: 22, color: colors.muted, marginTop: 8 },
  bottom: { borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 18, marginTop: 22, flexDirection: "row", alignItems: "flex-end", gap: 10 },
  priceLabel: { fontSize: 10, color: colors.muted, marginBottom: 5 },
  price: { fontSize: 26, fontWeight: "500", letterSpacing: -0.7, color: colors.ink },
  meta: { alignItems: "flex-end", gap: 5, maxWidth: "45%" },
  metaText: { color: colors.muted, fontSize: 11 },
});
