import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { ServiceSetupScreen } from "./src/screens/ServiceSetupScreen";

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <ServiceSetupScreen />
    </SafeAreaProvider>
  );
}
