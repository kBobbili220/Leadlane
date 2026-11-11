import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { ActivityIndicator, Alert, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { AuthProvider, useAuth } from "./src/auth/AuthProvider";
import { AuthScreen } from "./src/screens/AuthScreen";
import { ServiceSetupScreen } from "./src/screens/ServiceSetupScreen";
import { colors, common } from "./src/theme";

function RootScreen() {
  const auth = useAuth();
  if (auth.restoring) return <SafeAreaView style={[common.screen, { justifyContent: "center", alignItems: "center" }]}><ActivityIndicator color={colors.forest} size="large" /><Text style={[common.copy, { marginTop: 18 }]}>Opening your workspace…</Text></SafeAreaView>;
  if (auth.restoreError) return <SafeAreaView style={[common.screen, { justifyContent: "center", padding: 28 }]}><Text style={common.title}>Let’s reconnect.</Text><Text style={[common.copy, { marginVertical: 22 }]}>{auth.restoreError}</Text><Pressable accessibilityRole="button" onPress={() => void auth.retryRestore()} style={common.button}><Text style={common.buttonText}>Try again</Text></Pressable><Pressable accessibilityRole="button" onPress={() => void auth.signOut().catch(() => Alert.alert("Couldn’t clear session", "Please try again."))} style={common.secondary}><Text style={common.secondaryText}>Sign out</Text></Pressable></SafeAreaView>;
  if (!auth.session) return <AuthScreen />;
  return <View style={{ flex: 1 }}>
    {auth.storageWarning && <SafeAreaView edges={["top"]} style={{ backgroundColor: colors.lime, paddingHorizontal: 18, paddingBottom: 10 }}><Text style={{ fontSize: 12, color: colors.ink }}>You’re signed in for this session. We couldn’t remember it on this device.</Text><Pressable accessibilityRole="button" onPress={() => void auth.retryStorage().catch(() => Alert.alert("Couldn’t remember session", "Please try again."))}><Text style={{ fontWeight: "600", paddingTop: 8, color: colors.forest }}>Try remembering my session again</Text></Pressable></SafeAreaView>}
    <ServiceSetupScreen />
  </View>;
}

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <AuthProvider><RootScreen /></AuthProvider>
    </SafeAreaProvider>
  );
}
