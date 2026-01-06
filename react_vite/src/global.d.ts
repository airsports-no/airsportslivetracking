declare global {
  interface Document {
    configuration: {
      is_superuser: boolean;
      STATIC_FILE_LOCATION: string;
    };
  }
}

export {};
