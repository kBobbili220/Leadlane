import { Ionicons } from "@expo/vector-icons";
import { useRef, useState, type ReactNode } from "react";
import {
  AccessibilityInfo, ActivityIndicator, Keyboard, KeyboardAvoidingView, Modal, Platform,
  Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  buildServicePayload, ServiceRequestError,
  type FormErrors, type ServiceFormValues, type ServiceRecord,
} from "../../public/service-client.mjs";
import { createNativeService } from "../api/services.mjs";
import { CatalogSheet } from "../components/CatalogSheet";
import { ServiceCard } from "../components/ServiceCard";
import { getConnection } from "../connection";
import { colors, common } from "../theme";

const initialForm: ServiceFormValues = {
  name: "", description: "", pricingMode: "fixed", price: "", duration: "", unit: "vehicle", isActive: true,
};
const units = ["vehicle", "package", "hour", "service"];

function Field({ label, optional, required, error, children }: {
  label: string; optional?: boolean; required?: boolean; error?: string; children: ReactNode;
}) {
  return (
    <View style={styles.field}>
      <View style={styles.labelRow}><Text style={styles.label}>{label}{required && <Text style={{ color: "#829C65" }}> *</Text>}</Text>{optional && <Text style={styles.optional}>Optional</Text>}</View>
      {children}
      {!!error && <Text accessibilityLiveRegion="polite" style={styles.fieldError}>{error}</Text>}
    </View>
  );
}

export function ServiceSetupScreen() {
  const [form, setForm] = useState<ServiceFormValues>({ ...initialForm });
  const [errors, setErrors] = useState<FormErrors>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<{ message: string; uncertain: boolean } | null>(null);
  const [saved, setSaved] = useState<ServiceRecord | null>(null);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [unitOpen, setUnitOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const savingRef = useRef(false);
  const scroll = useRef<ScrollView>(null);
  const nameInput = useRef<TextInput>(null);
  const priceInput = useRef<TextInput>(null);
  const durationInput = useRef<TextInput>(null);

  function update<K extends keyof ServiceFormValues>(key: K, value: ServiceFormValues[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
    setErrors((previous) => ({ ...previous, [key]: undefined }));
  }

  async function submit() {
    if (savingRef.current) return;
    const result = buildServicePayload(form);
    setErrors(result.errors);
    setSaveError(null);
    if (!result.payload) {
      if (result.errors.name) { scroll.current?.scrollTo({ y: 0, animated: true }); nameInput.current?.focus(); }
      else if (result.errors.price) priceInput.current?.focus();
      else if (result.errors.duration) durationInput.current?.focus();
      AccessibilityInfo.announceForAccessibility("Please check the service details.");
      return;
    }
    savingRef.current = true;
    setSaving(true);
    Keyboard.dismiss();
    try {
      const record = await createNativeService(result.payload, getConnection());
      setSaved(record);
      scroll.current?.scrollTo({ y: 0, animated: false });
      AccessibilityInfo.announceForAccessibility("Your service has been saved.");
    } catch (caught) {
      const error = caught instanceof ServiceRequestError ? caught : new ServiceRequestError("We couldn’t confirm the save. Check your services before trying again.", { uncertain: true });
      setErrors(error.fields);
      setSaveError({ message: error.message, uncertain: error.uncertain });
      requestAnimationFrame(() => scroll.current?.scrollToEnd({ animated: true }));
      AccessibilityInfo.announceForAccessibility(error.message);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  function reset() {
    setSaved(null);
    setForm({ ...initialForm });
    setSaveError(null);
    setErrors({});
    setPreviewOpen(false);
    scroll.current?.scrollTo({ y: 0, animated: false });
  }

  const preview = buildServicePayload({ ...form, name: form.name.trim() || "Your signature service", duration: "" }).payload;

  return (
    <SafeAreaView style={common.screen} edges={["top", "left", "right"]}>
      <View style={styles.header}>
        <View style={styles.brand}><View style={styles.brandMark}><Ionicons name="sparkles" size={21} color={colors.forest} /></View><Text style={styles.brandText}>detailflow<Text style={{ color: "#94AE74" }}>.</Text></Text></View>
        <Pressable onPress={() => { Keyboard.dismiss(); setCatalogOpen(true); }} hitSlop={8} accessibilityRole="button" accessibilityLabel="Open my services" style={({ pressed }) => [styles.catalogLink, pressed && common.pressed]}>
          <Ionicons name="grid-outline" size={16} color={colors.forest} /><Text style={styles.catalogLinkText}>My services</Text>
        </Pressable>
      </View>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView ref={scroll} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" automaticallyAdjustKeyboardInsets={false}>
          {saved ? (
            <View style={styles.success}>
              <View style={styles.successMark}><Ionicons name="checkmark" size={40} color={colors.forest} /></View>
              <Text style={[common.eyebrow, { textAlign: "center", marginBottom: 18 }]}>ONE GOOD THING, ALL SET.</Text>
              <Text accessibilityRole="header" style={[common.title, styles.successTitle]}>Your service{"\n"}<Text style={{ color: "#718956", fontStyle: "italic" }}>is ready.</Text></Text>
              <Text style={styles.successCopy}>{saved.is_active ? "Added to your catalog and ready for your next quote." : "Saved as inactive. Make it available whenever you’re ready."}</Text>
              <ServiceCard service={saved} />
              <Pressable onPress={() => setCatalogOpen(true)} style={({ pressed }) => [common.button, { marginTop: 25 }, pressed && common.pressed]} accessibilityRole="button"><Text style={common.buttonText}>View my services</Text><Ionicons name="arrow-forward" size={19} color={colors.lime} /></Pressable>
              <Pressable onPress={reset} style={({ pressed }) => [common.secondary, pressed && common.pressed]} accessibilityRole="button"><Text style={common.secondaryText}>Add another service</Text><Ionicons name="add" size={20} color={colors.forest} /></Pressable>
            </View>
          ) : (
            <>
              <View style={styles.step}><View style={styles.stepCircle}><Text style={styles.stepNumber}>01</Text></View><Text style={styles.stepText}>LET’S BUILD YOUR CATALOG</Text></View>
              <Text accessibilityRole="header" style={[common.title, { marginTop: 23 }]}>Start with a{"\n"}great service.</Text>
              <Text style={[common.copy, { marginTop: 15, marginBottom: 27 }]}>Add what you do best. We’ll keep the details ready for your next customer.</Text>

              <View style={styles.formCard}>
                <Text style={styles.sectionTitle}><Text style={styles.sectionNumber}>01   </Text>The essentials</Text>
                <Field label="Service name" required error={errors.name}>
                  <TextInput ref={nameInput} value={form.name} onChangeText={(value) => update("name", value)} placeholder="e.g. Signature full detail" placeholderTextColor="#A8B09E" maxLength={200} style={[styles.input, !!errors.name && styles.invalid]} editable={!saving} accessibilityLabel="Service name, required" autoCapitalize="sentences" />
                </Field>
                <Field label="Description" optional>
                  <TextInput value={form.description} onChangeText={(value) => update("description", value)} placeholder="What’s included? Let your customers know what makes this service worth it." placeholderTextColor="#A8B09E" multiline textAlignVertical="top" style={[styles.input, styles.textarea]} editable={!saving} accessibilityLabel="Service description, optional" />
                  <Text style={styles.hint}>A few clear details go a long way.</Text>
                </Field>

                <View style={styles.divider} />
                <Text style={styles.sectionTitle}><Text style={styles.sectionNumber}>02   </Text>Price &amp; time</Text>
                <View style={styles.pricingRow} accessibilityRole="radiogroup">
                  {(["fixed", "custom"] as const).map((mode) => (
                    <Pressable key={mode} disabled={saving} accessibilityRole="radio" accessibilityState={{ checked: form.pricingMode === mode, disabled: saving }} onPress={() => { update("pricingMode", mode); setErrors((previous) => ({ ...previous, price: undefined })); }} style={[styles.pricingOption, form.pricingMode === mode && styles.pricingSelected]}>
                      <Ionicons name={form.pricingMode === mode ? "radio-button-on" : "radio-button-off"} size={17} color={form.pricingMode === mode ? "#547544" : "#C3CCB8"} />
                      <View style={{ flex: 1 }}><Text style={styles.pricingTitle}>{mode === "fixed" ? "Starting price" : "Custom quote"}</Text><Text style={styles.pricingCaption}>{mode === "fixed" ? "A clear starting point" : "Price it for each job"}</Text></View>
                    </Pressable>
                  ))}
                </View>
                <View style={styles.fieldRow}>
                  <View style={{ flex: 1 }}><Field label="Starting price" required={form.pricingMode === "fixed"} error={errors.price}><View style={[styles.inputGroup, form.pricingMode === "custom" && styles.disabledInput, !!errors.price && styles.invalid]}><Text style={styles.inputPrefix}>$</Text><TextInput ref={priceInput} value={form.price} onChangeText={(value) => update("price", value)} placeholder={form.pricingMode === "custom" ? "Custom" : "150.00"} placeholderTextColor="#A8B09E" keyboardType="decimal-pad" inputMode="decimal" maxLength={20} style={styles.amountInput} editable={!saving && form.pricingMode === "fixed"} accessibilityLabel="Starting price in US dollars" /><Text style={styles.suffix}>USD</Text></View></Field></View>
                  <View style={{ flex: 1 }}><Field label="Duration" optional error={errors.duration}><View style={[styles.inputGroup, !!errors.duration && styles.invalid]}><Ionicons name="time-outline" size={17} color={colors.muted} /><TextInput ref={durationInput} value={form.duration} onChangeText={(value) => update("duration", value)} placeholder="120" placeholderTextColor="#A8B09E" keyboardType="number-pad" inputMode="numeric" maxLength={10} style={styles.amountInput} editable={!saving} accessibilityLabel="Duration in minutes, optional" /><Text style={styles.suffix}>min</Text></View></Field></View>
                </View>
                {form.pricingMode === "custom" && <Text style={styles.customHint}>You’ll set the price when you prepare the customer’s quote.</Text>}
                <Field label="Priced per" error={errors.unit}>
                  <Pressable disabled={saving} onPress={() => { Keyboard.dismiss(); setUnitOpen(true); }} style={styles.unitButton} accessibilityRole="button" accessibilityLabel={`Priced per ${form.unit}. Change pricing unit.`}>
                    <Text style={styles.unitText}>{form.unit[0].toUpperCase() + form.unit.slice(1)}</Text><Ionicons name="chevron-down" size={17} color={colors.muted} />
                  </Pressable>
                </Field>
                <View style={styles.availability}><View style={{ flex: 1 }}><Text style={styles.availabilityTitle}>Ready for customers</Text><Text style={styles.availabilityHint}>Available for new quotes.</Text></View><Switch value={form.isActive} onValueChange={(value) => update("isActive", value)} disabled={saving} trackColor={{ false: "#D8DECF", true: "#547544" }} thumbColor="#FFFFFF" ios_backgroundColor="#D8DECF" accessibilityLabel="Make service available for new quotes" /></View>
              </View>
              <Pressable style={styles.previewToggle} onPress={() => setPreviewOpen((previous) => !previous)} accessibilityRole="button" accessibilityState={{ expanded: previewOpen }}><Ionicons name="eye-outline" size={17} color={colors.muted} /><Text style={styles.previewText}>{previewOpen ? "Hide service preview" : "Preview your service"}</Text><Ionicons name={previewOpen ? "chevron-up" : "chevron-down"} size={14} color={colors.muted} /></Pressable>
              {previewOpen && <ServiceCard preview service={{ name: form.name.trim() || "Your signature service", description: form.description.trim() || "The details that make your business stand out.", base_price_minor: form.pricingMode === "custom" ? null : preview?.base_price_minor ?? 0, estimated_duration_minutes: /^\d+$/.test(form.duration) && Number(form.duration) > 0 ? Number(form.duration) : null, unit_label: form.unit, is_active: form.isActive }} />}
              {!!saveError && <View accessibilityLiveRegion="assertive" style={styles.errorBox}><Text style={styles.errorTitle}>{saveError.uncertain ? "Let’s double-check that save." : "Something needs another look."}</Text><Text style={styles.errorCopy}>{saveError.message}</Text>{saveError.uncertain && <Pressable onPress={() => setCatalogOpen(true)} style={{ paddingTop: 12, minHeight: 40 }} accessibilityRole="button"><Text style={styles.errorLink}>Check my services ↗</Text></Pressable>}</View>}
              <Text style={styles.tagline}>A little more organized. A lot more ready.</Text>
            </>
          )}
        </ScrollView>
        {!saved && <SafeAreaView edges={["bottom"]} style={styles.footer}><Pressable disabled={saving} onPress={() => void submit()} accessibilityRole="button" accessibilityState={{ disabled: saving, busy: saving }} style={({ pressed }) => [common.button, (pressed || saving) && common.pressed]}>{saving ? <ActivityIndicator color={colors.lime} /> : null}<Text style={common.buttonText}>{saving ? "Saving your service…" : "Create service"}</Text>{!saving && <Ionicons name="arrow-forward" size={20} color={colors.lime} />}</Pressable><Text style={styles.footerHint}>✓  You can always edit these details later.</Text></SafeAreaView>}
      </KeyboardAvoidingView>
      <CatalogSheet visible={catalogOpen} onClose={() => setCatalogOpen(false)} />
      <Modal visible={unitOpen} transparent animationType="fade" onRequestClose={() => setUnitOpen(false)}>
        <View style={styles.unitOverlay}><Pressable style={StyleSheet.absoluteFill} onPress={() => setUnitOpen(false)} accessibilityRole="button" accessibilityLabel="Close pricing unit selector" /><SafeAreaView edges={["bottom"]} style={styles.unitSheet}><Text accessibilityRole="header" style={styles.unitHeading}>Priced per</Text>{units.map((unit) => <Pressable key={unit} onPress={() => { update("unit", unit); setUnitOpen(false); }} style={styles.unitChoice} accessibilityRole="radio" accessibilityState={{ checked: form.unit === unit }}><Text style={styles.unitText}>{unit[0].toUpperCase() + unit.slice(1)}</Text>{form.unit === unit && <Ionicons name="checkmark" size={22} color={colors.forest} />}</Pressable>)}<Pressable onPress={() => setUnitOpen(false)} style={common.secondary} accessibilityRole="button"><Text style={common.secondaryText}>Cancel</Text></Pressable></SafeAreaView></View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 22, paddingVertical: 17, borderBottomWidth: 1, borderBottomColor: colors.line, gap: 12 },
  brand: { flexDirection: "row", alignItems: "center", gap: 8 },
  brandMark: { backgroundColor: colors.lime, width: 31, height: 31, borderRadius: 10, justifyContent: "center", alignItems: "center" },
  brandText: { fontSize: 24, fontWeight: "600", letterSpacing: -1.1, color: colors.ink },
  catalogLink: { flexDirection: "row", alignItems: "center", gap: 6, minHeight: 40 },
  catalogLinkText: { fontSize: 12, color: colors.forest },
  content: { padding: 20, paddingTop: 30, maxWidth: 600, width: "100%", alignSelf: "center" },
  step: { flexDirection: "row", alignItems: "center", gap: 9 },
  stepCircle: { width: 25, height: 25, borderRadius: 13, backgroundColor: "#E7EFDA", justifyContent: "center", alignItems: "center" },
  stepNumber: { fontSize: 10, color: "#688051", fontWeight: "600" },
  stepText: { fontSize: 9, letterSpacing: 1.3, color: "#748465", fontWeight: "600" },
  formCard: { padding: 21, paddingBottom: 5, borderRadius: 15, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.white },
  sectionTitle: { fontSize: 14, fontWeight: "600", color: colors.ink, marginBottom: 24 },
  sectionNumber: { color: "#9CA88E", fontSize: 11, fontWeight: "400" },
  field: { marginBottom: 21 },
  labelRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 4, marginBottom: 9 },
  label: { fontSize: 12, color: colors.ink, fontWeight: "500" },
  optional: { fontSize: 10, color: "#99A18F" },
  input: { minHeight: 49, paddingHorizontal: 13, paddingVertical: 12, fontSize: 15, borderWidth: 1, borderColor: colors.line, borderRadius: 8, backgroundColor: colors.white, color: colors.ink },
  textarea: { minHeight: 105, fontSize: 14, lineHeight: 22 },
  hint: { fontSize: 10, color: "#99A18F", marginTop: 7 },
  divider: { borderTopWidth: 1, borderTopColor: "#EDF0E8", marginBottom: 24, marginTop: 3 },
  pricingRow: { flexDirection: "row", gap: 8, marginBottom: 23 },
  pricingOption: { flex: 1, flexDirection: "row", alignItems: "center", gap: 6, borderWidth: 1, borderColor: colors.line, borderRadius: 9, paddingHorizontal: 9, paddingVertical: 14, minHeight: 71 },
  pricingSelected: { backgroundColor: "#F3F7EB", borderColor: "#9FB68C" },
  pricingTitle: { fontSize: 11, fontWeight: "600", color: colors.ink },
  pricingCaption: { fontSize: 9, color: colors.muted, marginTop: 5, lineHeight: 13 },
  fieldRow: { flexDirection: "row", gap: 12 },
  inputGroup: { flexDirection: "row", alignItems: "center", borderWidth: 1, borderColor: colors.line, borderRadius: 8, paddingHorizontal: 11, minHeight: 49, gap: 6 },
  inputPrefix: { fontSize: 15, color: colors.muted },
  amountInput: { flex: 1, minWidth: 0, minHeight: 47, fontSize: 15, color: colors.ink, paddingVertical: 10 },
  suffix: { fontSize: 10, color: "#99A18F" },
  disabledInput: { backgroundColor: "#F3F5EF" },
  fieldError: { fontSize: 11, lineHeight: 17, color: colors.error, marginTop: 7 },
  invalid: { borderColor: "#C77C70" },
  customHint: { backgroundColor: colors.light, color: "#6B8059", fontSize: 11, lineHeight: 18, padding: 12, borderRadius: 7, marginBottom: 20 },
  unitButton: { minHeight: 49, borderWidth: 1, borderColor: colors.line, borderRadius: 8, paddingHorizontal: 13, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  unitText: { color: colors.ink, fontSize: 15 },
  availability: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 20, borderTopWidth: 1, borderTopColor: "#EDF0E8" },
  availabilityTitle: { color: colors.ink, fontSize: 12, fontWeight: "500" },
  availabilityHint: { color: colors.muted, fontSize: 11, marginTop: 5 },
  previewToggle: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, minHeight: 53, marginTop: 5 },
  previewText: { color: colors.muted, fontSize: 12 },
  footer: { paddingHorizontal: 20, paddingTop: 14, backgroundColor: colors.paper, borderTopWidth: 1, borderTopColor: colors.line },
  footerHint: { textAlign: "center", fontSize: 10, color: colors.muted, paddingVertical: 12 },
  tagline: { textAlign: "center", fontSize: 10, color: "#A0A993", marginVertical: 15 },
  errorBox: { backgroundColor: colors.errorBackground, borderWidth: 1, borderColor: "#EBD8CE", padding: 16, borderRadius: 10, marginTop: 15 },
  errorTitle: { fontSize: 13, fontWeight: "600", color: colors.error },
  errorCopy: { fontSize: 12, lineHeight: 21, color: colors.error, marginTop: 7 },
  errorLink: { fontSize: 12, fontWeight: "600", color: colors.error },
  success: { paddingTop: 20, paddingBottom: 30 },
  successMark: { width: 77, height: 77, backgroundColor: "#E4EDCF", borderRadius: 25, justifyContent: "center", alignItems: "center", alignSelf: "center", marginBottom: 29, transform: [{ rotate: "-7deg" }] },
  successTitle: { textAlign: "center", fontSize: 56, lineHeight: 61 },
  successCopy: { textAlign: "center", fontSize: 14, lineHeight: 24, color: colors.muted, maxWidth: 290, alignSelf: "center", marginTop: 17, marginBottom: 29 },
  unitOverlay: { flex: 1, justifyContent: "flex-end", backgroundColor: "#102B256B" },
  unitSheet: { backgroundColor: colors.paper, borderTopLeftRadius: 23, borderTopRightRadius: 23, padding: 24 },
  unitHeading: { color: colors.ink, fontSize: 20, fontWeight: "600", marginBottom: 17 },
  unitChoice: { minHeight: 55, flexDirection: "row", justifyContent: "space-between", alignItems: "center", borderBottomWidth: 1, borderBottomColor: colors.line },
});
