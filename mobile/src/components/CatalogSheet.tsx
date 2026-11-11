import { Ionicons } from "@expo/vector-icons";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, FlatList, Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { ServiceRecord } from "../../public/service-client.mjs";
import { listNativeServices } from "../api/services.mjs";
import { useAuthenticatedConnection } from "../auth/AuthProvider";
import { colors, common, serif } from "../theme";
import { ServiceCard } from "./ServiceCard";

export function CatalogSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const connection = useAuthenticatedConnection();
  const [items, setItems] = useState<ServiceRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const generation = useRef(0);
  const busy = useRef(false);

  async function load(reset: boolean) {
    if (busy.current) return;
    const request = ++generation.current;
    busy.current = true;
    setLoading(true);
    setRefreshing(reset && items.length > 0);
    setError(null);
    try {
      const rows = await listNativeServices({ offset: reset ? 0 : items.length, limit: 50 }, connection);
      if (request !== generation.current) return;
      setItems((previous) => reset ? rows : [...previous, ...rows]);
      setHasMore(rows.length === 50);
    } catch (caught) {
      if (request === generation.current) setError(caught instanceof Error ? caught.message : "We couldn’t load your services.");
    } finally {
      if (request === generation.current) {
        busy.current = false;
        setLoading(false);
        setRefreshing(false);
      }
    }
  }

  useEffect(() => {
    generation.current += 1;
    busy.current = false;
    if (visible) void load(true);
    return () => { generation.current += 1; busy.current = false; };
  }, [visible]);

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView style={common.screen} edges={["top", "left", "right", "bottom"]}>
        <View style={styles.header}>
          <View style={{ flex: 1 }}><Text style={common.eyebrow}>YOUR WORKSPACE</Text><Text accessibilityRole="header" style={styles.title}>The service catalog.</Text></View>
          <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close service catalog" hitSlop={10} style={({ pressed }) => [styles.close, pressed && common.pressed]}>
            <Ionicons name="close" size={22} color={colors.forest} />
          </Pressable>
        </View>
        <Text style={styles.subtitle}>Everything you offer, in one place.</Text>
        <FlatList
          data={items}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => <ServiceCard service={item} />}
          contentContainerStyle={styles.list}
          ItemSeparatorComponent={() => <View style={{ height: 14 }} />}
          refreshing={refreshing}
          onRefresh={() => void load(true)}
          ListEmptyComponent={loading ? <ActivityIndicator color={colors.forest} style={{ marginTop: 45 }} /> : !error ? <Text style={styles.empty}>A clean slate. Add your first service to get started.</Text> : null}
          ListFooterComponent={(
            <View style={{ paddingBottom: 20 }}>
              {!!error && <View accessibilityLiveRegion="polite" style={styles.error}><Text style={styles.errorText}>{error}</Text><Pressable disabled={loading} onPress={() => void load(items.length === 0)} style={common.secondary} accessibilityRole="button"><Text style={common.secondaryText}>Try again</Text></Pressable></View>}
              {hasMore && !error && <Pressable disabled={loading} onPress={() => void load(false)} style={common.secondary} accessibilityRole="button">{loading ? <ActivityIndicator color={colors.forest} /> : <Text style={common.secondaryText}>Load more services</Text>}</Pressable>}
            </View>
          )}
        />
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: 24, paddingTop: 22, flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 },
  title: { fontFamily: serif, fontSize: 32, letterSpacing: -0.9, color: colors.ink, marginTop: 10 },
  close: { height: 42, width: 42, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: colors.line, borderRadius: 22 },
  subtitle: { fontSize: 13, color: colors.muted, marginTop: 13, paddingHorizontal: 24, marginBottom: 24 },
  list: { paddingHorizontal: 20, paddingBottom: 25 },
  empty: { fontSize: 14, lineHeight: 24, textAlign: "center", color: colors.muted, marginTop: 55, padding: 20 },
  error: { paddingTop: 18 },
  errorText: { fontSize: 13, lineHeight: 22, color: colors.error },
});
