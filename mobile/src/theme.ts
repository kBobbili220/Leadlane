import { Platform, StyleSheet } from "react-native";

export const colors = {
  paper: "#F8F9F5", white: "#FFFFFF", forest: "#203C32", ink: "#243B31",
  lime: "#DBEDB8", muted: "#87917E", light: "#EFF4E6", line: "#E1E7D9",
  error: "#9A463A", errorBackground: "#FCF1ED",
};
export const serif = Platform.select({ ios: "Georgia", android: "serif", default: "Georgia" });
export const common = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  eyebrow: { fontSize: 10, letterSpacing: 1.6, fontWeight: "600", color: colors.muted },
  title: { fontFamily: serif, fontSize: 44, lineHeight: 49, letterSpacing: -1.6, color: colors.ink },
  copy: { fontSize: 14, lineHeight: 23, color: colors.muted },
  button: { minHeight: 54, borderRadius: 10, backgroundColor: colors.forest, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 12, paddingHorizontal: 20 },
  buttonText: { color: colors.white, fontSize: 15, fontWeight: "600" },
  secondary: { minHeight: 50, borderWidth: 1, borderColor: colors.line, borderRadius: 10, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 10, marginTop: 12 },
  secondaryText: { color: colors.forest, fontSize: 14, fontWeight: "600" },
  pressed: { opacity: 0.7 },
});
