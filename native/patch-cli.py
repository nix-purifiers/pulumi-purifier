from pathlib import Path

p = Path("cmd/pulumi/plugin/plugin.go")
s = p.read_text().replace('"context"', '"context"\n "encoding/json"\n "os"')
s = s.replace(
    "func NewPluginCmd() *cobra.Command {",
    'func purifierDownloadCmd() *cobra.Command {\n return &cobra.Command{Use: "purifier-download FILE", Hidden: true, Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {\n data, err := os.ReadFile(args[0]); if err != nil { return err }\n var specs []workspace.PluginDescriptor\n if err = json.Unmarshal(data, &specs); err != nil { return err }\n for _, spec := range specs {\n file, err := workspace.DownloadToFile(cmd.Context(), spec, nil, nil)\n if err != nil { return err }; file.Close(); os.Remove(file.Name())\n }\n return nil\n }}\n}\n\nfunc purifierSpecsCmd() *cobra.Command {\n return &cobra.Command{Use: "purifier-specs", Hidden: true, RunE: func(cmd *cobra.Command, args []string) error {\n  plugins, err := getProjectPlugins(cmd.Context())\n  if err != nil { return err }\n  return json.NewEncoder(os.Stdout).Encode(plugins)\n }}\n}\n\nfunc NewPluginCmd() *cobra.Command {',
)
s = s.replace(
    "return cmd\n}",
    "cmd.AddCommand(purifierSpecsCmd())\n cmd.AddCommand(purifierDownloadCmd())\n return cmd\n}",
    1,
)
p.write_text(s)
