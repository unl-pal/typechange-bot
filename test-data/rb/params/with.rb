# typed: true
extend T::Sig

sig {params(name: String)}
def main(name)
  puts "Hello, #{name}!"
  name.length
end
