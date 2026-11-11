import Constants from "expo-constants";
import type { NativeConnection } from "./api/services.mjs";

export function getConnection(): NativeConnection {
  return {
    apiUrl: process.env.EXPO_PUBLIC_API_URL,
    hostUri: Constants.expoConfig?.hostUri,
  };
}
