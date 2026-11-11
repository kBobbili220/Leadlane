import { Ionicons } from "@expo/vector-icons";
import { useRef, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAuth } from "../auth/AuthProvider";
import { colors, common } from "../theme";

export function AuthScreen() {
  const { signIn, signUp } = useAuth();
  const [registering, setRegistering] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [name, setName] = useState("");
  const [business, setBusiness] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busyRef = useRef(false);

  async function submit() {
    if (busyRef.current) return;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) || email.trim().length > 254) { setError("Enter a valid email address."); return; }
    if (!password || password.length > 128 || (registering && password.length < 12)) { setError(registering ? "Use a password of 12–128 characters." : "Enter your password."); return; }
    if (registering && (!name.trim() || !business.trim())) { setError("Enter your name and your business name."); return; }
    if (registering && password !== confirmation) { setError("Your passwords don’t match."); return; }
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try {
      if (registering) await signUp({ email: email.trim(), password, full_name: name.trim(), business_name: business.trim() });
      else await signIn({ email: email.trim(), password });
      setPassword("");
      setConfirmation("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "We couldn’t sign you in. Please try again."); }
    finally { busyRef.current = false; setBusy(false); }
  }

  return (
    <SafeAreaView style={common.screen}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.content}>
          <View style={styles.brand}><View style={styles.mark}><Ionicons name="sparkles" size={24} color={colors.forest} /></View><Text style={styles.brandText}>detailflow<Text style={{ color: "#94AE74" }}>.</Text></Text></View>
          <Text style={[common.eyebrow, { marginTop: 45 }]}>YOUR BUSINESS, IN ORDER.</Text>
          <Text accessibilityRole="header" style={[common.title, { marginTop: 19 }]}>{registering ? "A fresh start\nfor your business." : "Welcome\nback."}</Text>
          <Text style={[common.copy, { marginTop: 17, marginBottom: 28 }]}>{registering ? "Create your owner account. We’ll get your workspace ready for your first service." : "Sign in to your workspace and pick up where you left off."}</Text>
          <View style={styles.card}>
            {registering && <>
              <Text style={styles.label}>Your name</Text><TextInput accessibilityLabel="Your full name" value={name} onChangeText={setName} maxLength={200} editable={!busy} placeholder="Alex Morgan" placeholderTextColor="#A8B09E" textContentType="name" style={styles.input} />
              <Text style={styles.label}>Business name</Text><TextInput accessibilityLabel="Business name" value={business} onChangeText={setBusiness} maxLength={200} editable={!busy} placeholder="Your detailing business" placeholderTextColor="#A8B09E" style={styles.input} />
            </>}
            <Text style={styles.label}>Email address</Text><TextInput accessibilityLabel="Email address" value={email} onChangeText={setEmail} maxLength={254} editable={!busy} placeholder="you@yourbusiness.com" placeholderTextColor="#A8B09E" autoCapitalize="none" autoCorrect={false} keyboardType="email-address" textContentType="emailAddress" autoComplete="email" style={styles.input} />
            <Text style={styles.label}>Password</Text><View style={styles.passwordRow}><TextInput accessibilityLabel="Password" value={password} onChangeText={setPassword} maxLength={128} editable={!busy} placeholder={registering ? "At least 12 characters" : "Your password"} placeholderTextColor="#A8B09E" autoCapitalize="none" autoCorrect={false} secureTextEntry={!showPassword} textContentType={registering ? "newPassword" : "password"} autoComplete={registering ? "new-password" : "current-password"} style={styles.passwordInput} /><Pressable onPress={() => setShowPassword((value) => !value)} accessibilityRole="button" accessibilityLabel={showPassword ? "Hide password" : "Show password"} style={styles.eye}><Ionicons name={showPassword ? "eye-off-outline" : "eye-outline"} size={21} color={colors.muted} /></Pressable></View>
            {registering && <><Text style={styles.label}>Confirm password</Text><TextInput accessibilityLabel="Confirm password" value={confirmation} onChangeText={setConfirmation} maxLength={128} editable={!busy} placeholder="Enter your password again" placeholderTextColor="#A8B09E" secureTextEntry autoCapitalize="none" autoCorrect={false} textContentType="newPassword" style={styles.input} /></>}
            {!!error && <Text accessibilityLiveRegion="assertive" style={styles.error}>{error}</Text>}
            <Pressable disabled={busy} accessibilityRole="button" accessibilityState={{ busy, disabled: busy }} onPress={() => void submit()} style={({ pressed }) => [common.button, { marginTop: 6 }, (pressed || busy) && common.pressed]}>{busy && <ActivityIndicator color={colors.lime} />}<Text style={common.buttonText}>{busy ? "Getting things ready…" : registering ? "Create my workspace" : "Sign in"}</Text>{!busy && <Ionicons name="arrow-forward" size={20} color={colors.lime} />}</Pressable>
          </View>
          <View style={styles.toggleRow}><Text style={styles.toggleCopy}>{registering ? "Already have an account?" : "New to Detailflow?"}</Text><Pressable disabled={busy} onPress={() => { setRegistering((value) => !value); setError(null); setPassword(""); setConfirmation(""); }} accessibilityRole="button" style={{ paddingVertical: 15 }}><Text style={styles.toggleLink}>{registering ? "Sign in" : "Create an account"}</Text></Pressable></View>
          <Text style={styles.tagline}>Less admin. More shine.</Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 25, paddingBottom: 35, flexGrow: 1, maxWidth: 540, width: "100%", alignSelf: "center" },
  brand: { flexDirection: "row", alignItems: "center", gap: 9, marginTop: 12 },
  mark: { backgroundColor: colors.lime, height: 36, width: 36, borderRadius: 11, alignItems: "center", justifyContent: "center" },
  brandText: { color: colors.ink, fontSize: 28, letterSpacing: -1.2, fontWeight: "600" },
  card: { backgroundColor: colors.white, borderWidth: 1, borderColor: colors.line, borderRadius: 16, padding: 21 },
  label: { color: colors.ink, fontSize: 12, fontWeight: "500", marginBottom: 9 },
  input: { minHeight: 51, borderWidth: 1, borderColor: colors.line, borderRadius: 8, padding: 13, color: colors.ink, fontSize: 15, marginBottom: 20 },
  passwordRow: { borderWidth: 1, borderColor: colors.line, borderRadius: 8, flexDirection: "row", alignItems: "center", minHeight: 51, marginBottom: 20 },
  passwordInput: { flex: 1, color: colors.ink, fontSize: 15, minWidth: 0, padding: 13 },
  eye: { padding: 12 },
  error: { color: colors.error, backgroundColor: colors.errorBackground, padding: 13, borderRadius: 8, fontSize: 12, lineHeight: 20, marginBottom: 16 },
  toggleRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", flexWrap: "wrap", gap: 7, marginTop: 14 },
  toggleCopy: { color: colors.muted, fontSize: 12 },
  toggleLink: { color: colors.forest, fontSize: 12, fontWeight: "600" },
  tagline: { color: colors.muted, fontSize: 10, textAlign: "center", marginTop: 15 },
});
